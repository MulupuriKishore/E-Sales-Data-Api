from flask import Flask,request,jsonify,g
import pandas as pd
from database import db
from models import Sale
import time
from collections import defaultdict, deque
import logging

app=Flask(__name__)

# Rate limiting configuration
RATE_LIMIT = 1
RATE_WINDOW = 5

request_history = defaultdict(deque)


@app.before_request
def limit_requests():
    now = time.monotonic()
    client_ip = request.remote_addr or "unknown"

    # Get this client's request timestamps
    timestamps = request_history[client_ip]

    # Remove requests older than 60 seconds
    while timestamps and now - timestamps[0] >= RATE_WINDOW:
        timestamps.popleft()

    # Reject requests when the limit is reached
    if len(timestamps) >= RATE_LIMIT:
        return jsonify({
            "error": "Rate limit exceeded",
            "message": "Try again after a short wait."
        }), 429

    timestamps.append(now)
    g.request_start_time = now

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

app.logger.setLevel(logging.INFO)

@app.after_request
def log_request(response):
    start_time = getattr(
        g, "request_start_time", time.monotonic()
    )

    duration_ms = (time.monotonic() - start_time) * 1000

    app.logger.info(
        "method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.path,
        response.status_code,
        duration_ms
    )

    return response

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Not found",
        "message": "The requested resource does not exist."
    }), 404


@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error(
        "Internal server error: %s", error
    )

    return jsonify({
        "error": "Internal server error",
        "message": "Something went wrong on the server."
    }), 500

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sales.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
with app.app_context():
  db.create_all()

  with db.engine.begin() as connection:
    connection.exec_driver_sql("""
    CREATE INDEX IF NOT EXISTS ix_sales_city
    ON sales(city)
    """
    )

def load_data():
    with app.app_context():
        with db.engine.connect() as connection:
            result = connection.exec_driver_sql(
                "SELECT * FROM sales"
            )

            rows = result.fetchall()
            columns = result.keys()

            df = pd.DataFrame(rows, columns=columns)

    df["order_date"] = pd.to_datetime(df["order_date"])
    df["revenue"] = df["price"] * df["quantity"]

    return df

@app.get('/')
def home():
  return{
    "message":"E Sales Data Analytics API"
  }

@app.get("/sales")
def get_sales():
  df = load_data()
  return df.to_dict(orient="records")

summary_cache={
  "data":None,
  "expires_at":0
}
CACHE_TTL = 60

@app.get("/sales/summary")
def sales_summary():
  now = time.time()
  if(summary_cache["data"] is not None and now < summary_cache["expires_at"]):
    return jsonify(summary_cache["data"])
  df = load_data()
  total_orders=int(len(df))
  total_revenue=float(df["revenue"].sum())
  average_order_value=float(df["revenue"].mean())
  return{
    "total_orders": total_orders,
    "total_revenue": total_revenue,
    "average_order_value": average_order_value
  }

@app.get("/sales/top-product")
def top_products():
  df = load_data()
  product_sales=(
    df.groupby("product",as_index=False)["revenue"]
    .sum()
    .sort_values("revenue",ascending=False)
    .head(2)
  )
  return product_sales.to_dict(orient="records")

@app.get("/sales/montly")
def monthly_sales():
  df = load_data()
  monthly_sales=(
    df.groupby(df["order_date"].dt.to_period("M"))["revenue"]
    .sum()
  )
  return{
    str(month):revenue
    for month,revenue in monthly_sales.items()
  }

@app.get("/sales/cities")
def city_sales():
  df = load_data()
  city_sales=(
    df.groupby("city").agg(
      total_orders=("order_id","count"),
      total_quantity=("quantity","sum"),
      total_revenue=("revenue","sum")
    )
    .reset_index()
    .sort_values("total_revenue",ascending=False)
  )
  return city_sales.to_dict(orient="records")

@app.get("/sales/customers")
def customer_sales():
  df = load_data()
  city=request.args.get("city")
  
  if city:
    city = city.strip()
    matching_cities = df[df["city"].str.strip().str.lower() == city.lower()]
  
  if matching_cities.empty:
    return{
      "error":"City not found"
    },404
  df = matching_cities
  try:
    page=request.args.get("page",default=1,type=int)
    pagesize=request.args.get("pagesize",default=5,type=int)
  except ValueError:
    return jsonify({
      "error":"page and limit must be integers"
    }),400

  if page<1:
    return{
      "error":"Page must be at least 1"
    },400

  if pagesize<1 or pagesize>100:
    return{
      "error":"Pagesize must be between 1 and 100"
    },400

  customer_sales=(
    df.groupby("customer").agg(
      total_orders=("order_id","count"),
      total_quantity=("quantity","sum"),
      total_spent=("revenue","sum")
    )
    .reset_index()
    .sort_values("total_spent",ascending=False)
  )

  total_customers = len(customer_sales)
  start = (page-1)*pagesize
  end = start + pagesize

  data = customer_sales.iloc[start:end]

  total_pages = (total_customers + pagesize -1)//pagesize

  return {
    "data":data.to_dict(orient="records"),
    "pagination":{
      "page":page,
      "pagesize":pagesize,
      "total_customers":total_customers,
      "total_pages":total_pages
    }
  }

if __name__=="__main__":
  app.run(debug=True,ssl_context='adhoc')