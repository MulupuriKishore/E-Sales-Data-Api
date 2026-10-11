from database import db


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.Integer,
        unique=True,
        nullable=False
    )

    order_date = db.Column(db.Date, nullable=False)

    customer = db.Column(db.String(100), nullable=False)

    product = db.Column(db.String(100), nullable=False)

    category = db.Column(db.String(100))

    price = db.Column(db.Float, nullable=False)

    quantity = db.Column(db.Integer, nullable=False)

    city = db.Column(db.String(100), nullable=False)

    payment_method = db.Column(db.String(50))