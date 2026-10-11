import pandas as pd
from app import app
from database import db
from models import Sale

CSV_PATH = "data/raw/sales.csv"

def import_sales():
  df = pd.read_csv(CSV_PATH)

  df["order_date"] = pd.to_datetime(
    df["order_date"],
    dayfirst = True,
    errors = "raise"
  ).dt.date

  with app.app_context():
    existing_ids = {
      order_id
      for (order_id,) in db.session.query(Sale.order_id).all()
    }

    df = df[~df["order_id"].isin(existing_ids)]

    if df.empty:
      print("No new sales to import. ")
      return

    records = df.to_dict(orient = "records")

    db.session.bulk_insert_mappings(Sale,records)
    db.session.commit()

    print(f"Imported {len(records)} new sales.")

if __name__ == "__main__":
  print("Starting")
  import_sales()
  print("Finished")