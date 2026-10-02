from decimal import Decimal

from app import app
from extensions import db
from models import Product


SHOPIER_URL = (
    "https://www.shopier.com/semihakvaryum/50488190"
)


with app.app_context():

    existing = db.session.scalar(
        db.select(Product).where(
            Product.slug
            == "test-akvaryum-urunu"
        )
    )

    if existing:
        print(
            "Ürün zaten mevcut:",
            existing.name,
        )

    else:

        product = Product(
            slug="test-akvaryum-urunu",

            name=(
                "Test Akvaryum Ürünü"
            ),

            short_description=(
                "Semih Akvaryum mağaza "
                "altyapısı test ürünü."
            ),

            description=(
                "Bu ürün mağaza altyapısını "
                "test etmek amacıyla eklendi.\n\n"
                "Shopier ödeme bağlantısı "
                "üzerinden güvenli şekilde "
                "satın alınabilir."
            ),

            category="Ekipman",

            price=Decimal(
                "349.90"
            ),

            stock=10,

            image_url=None,

            shopier_product_id=None,

            shopier_url=SHOPIER_URL,

            is_active=True,

            is_featured=True,
        )

        db.session.add(
            product
        )

        db.session.commit()

        print(
            "Ürün oluşturuldu:",
            product.id,
            product.name,
        )