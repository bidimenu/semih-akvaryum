import hmac
import os
import re
import secrets
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from extensions import db
from models import Product


shop_admin_bp = Blueprint(
    "shop_admin",
    __name__,
)


def _admin_emails():
    raw = os.getenv(
        "SHOP_ADMIN_EMAILS",
        os.getenv("SHOP_ADMIN_EMAIL", ""),
    )

    return {
        item.strip().lower()
        for item in raw.split(",")
        if item.strip()
    }


def _require_shop_admin():
    if not current_user.is_authenticated:
        abort(401)

    email = (
        getattr(current_user, "email", "")
        or ""
    ).strip().lower()

    allowed = _admin_emails()

    if not allowed or email not in allowed:
        abort(403)


def _csrf_token():
    token = session.get("shop_admin_csrf")

    if not token:
        token = secrets.token_urlsafe(32)
        session["shop_admin_csrf"] = token

    return token


def _validate_csrf():
    expected = session.get("shop_admin_csrf", "")
    received = request.form.get("csrf_token", "")

    if (
        not expected
        or not received
        or not hmac.compare_digest(
            expected,
            received,
        )
    ):
        abort(400)


def _slugify(value):
    normalized = unicodedata.normalize(
        "NFKD",
        value or "",
    )

    ascii_value = "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )

    ascii_value = ascii_value.lower()
    ascii_value = re.sub(
        r"[^a-z0-9]+",
        "-",
        ascii_value,
    )

    return ascii_value.strip("-")[:160]


def _safe_url(value, *, shopier_only=False):
    value = (value or "").strip()

    if not value:
        return None

    try:
        parsed = urlparse(value)
    except ValueError:
        return None

    if parsed.scheme not in {"http", "https"}:
        return None

    host = (parsed.hostname or "").lower()

    if not host:
        return None

    if shopier_only:
        if not (
            host == "shopier.com"
            or host.endswith(".shopier.com")
        ):
            return None

    return value


def _parse_price(raw):
    value = (
        (raw or "")
        .strip()
        .replace(" ", "")
    )

    if not value:
        raise ValueError(
            "Fiyat zorunludur."
        )

    if "," in value:
        value = (
            value
            .replace(".", "")
            .replace(",", ".")
        )

    try:
        price = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(
            "Geçerli bir fiyat gir."
        ) from exc

    if price < 0:
        raise ValueError(
            "Fiyat negatif olamaz."
        )

    return price.quantize(
        Decimal("0.01")
    )


def _parse_stock(raw):
    try:
        stock = int(
            (raw or "").strip()
        )
    except ValueError as exc:
        raise ValueError(
            "Stok adedi tam sayı olmalı."
        ) from exc

    if stock < 0:
        raise ValueError(
            "Stok negatif olamaz."
        )

    return stock


def _form_payload():
    return {
        "name": request.form.get("name", "").strip(),
        "slug": request.form.get("slug", "").strip(),
        "category": request.form.get("category", "").strip(),
        "price": request.form.get("price", "").strip(),
        "stock": request.form.get("stock", "0").strip(),
        "short_description": request.form.get(
            "short_description", ""
        ).strip(),
        "description": request.form.get(
            "description", ""
        ).strip(),
        "image_url": request.form.get(
            "image_url", ""
        ).strip(),
        "shopier_product_id": request.form.get(
            "shopier_product_id", ""
        ).strip(),
        "shopier_url": request.form.get(
            "shopier_url", ""
        ).strip(),
        "is_active": request.form.get("is_active") == "1",
        "is_featured": request.form.get("is_featured") == "1",
    }


def _validate_product_form(
    payload,
    *,
    current_product_id=None,
):
    errors = []

    if len(payload["name"]) < 2:
        errors.append(
            "Ürün adı en az 2 karakter olmalı."
        )

    slug = (
        _slugify(payload["slug"])
        if payload["slug"]
        else _slugify(payload["name"])
    )

    if not slug:
        errors.append(
            "Geçerli bir ürün URL adı oluşturulamadı."
        )

    if slug:
        existing = db.session.scalar(
            db.select(Product).where(
                Product.slug == slug
            )
        )

        if (
            existing is not None
            and existing.id != current_product_id
        ):
            errors.append(
                "Bu ürün URL adı başka bir üründe kullanılıyor."
            )

    try:
        price = _parse_price(
            payload["price"]
        )
    except ValueError as exc:
        price = None
        errors.append(str(exc))

    try:
        stock = _parse_stock(
            payload["stock"]
        )
    except ValueError as exc:
        stock = None
        errors.append(str(exc))

    shopier_url = _safe_url(
        payload["shopier_url"],
        shopier_only=True,
    )

    if not shopier_url:
        errors.append(
            "Geçerli bir Shopier ürün linki gir."
        )

    image_url = None

    if payload["image_url"]:
        image_url = _safe_url(
            payload["image_url"]
        )

        if not image_url:
            errors.append(
                "Ürün görseli için geçerli bir http/https URL gir."
            )

    return {
        "errors": errors,
        "slug": slug,
        "price": price,
        "stock": stock,
        "shopier_url": shopier_url,
        "image_url": image_url,
    }


def _apply_product_data(
    product,
    payload,
    validated,
):
    product.name = payload["name"]
    product.slug = validated["slug"]
    product.category = payload["category"] or None
    product.price = validated["price"]
    product.stock = validated["stock"]
    product.short_description = (
        payload["short_description"] or None
    )
    product.description = (
        payload["description"] or None
    )
    product.image_url = validated["image_url"]
    product.shopier_product_id = (
        payload["shopier_product_id"] or None
    )
    product.shopier_url = validated["shopier_url"]
    product.is_active = payload["is_active"]
    product.is_featured = payload["is_featured"]


@shop_admin_bp.context_processor
def shop_admin_context():
    return {
        "shop_admin_csrf_token": _csrf_token,
    }


@shop_admin_bp.get("/admin/urunler")
@login_required
def product_list():
    _require_shop_admin()

    products = db.session.scalars(
        db.select(Product)
        .order_by(
            Product.created_at.desc()
        )
    ).all()

    return render_template(
        "admin_products.html",
        products=products,
    )


@shop_admin_bp.route(
    "/admin/urunler/yeni",
    methods=["GET", "POST"],
)
@login_required
def product_create():
    _require_shop_admin()

    if request.method == "POST":
        _validate_csrf()

        payload = _form_payload()
        validated = _validate_product_form(
            payload
        )

        if validated["errors"]:
            for error in validated["errors"]:
                flash(error, "error")

            return render_template(
                "admin_product_form.html",
                product=None,
                form=payload,
                mode="create",
            ), 400

        product = Product()

        _apply_product_data(
            product,
            payload,
            validated,
        )

        db.session.add(product)
        db.session.commit()

        flash(
            "Ürün mağazaya eklendi.",
            "success",
        )

        return redirect(
            url_for(
                "shop_admin.product_list"
            )
        )

    return render_template(
        "admin_product_form.html",
        product=None,
        form={
            "name": "",
            "slug": "",
            "category": "",
            "price": "",
            "stock": "0",
            "short_description": "",
            "description": "",
            "image_url": "",
            "shopier_product_id": "",
            "shopier_url": "",
            "is_active": True,
            "is_featured": False,
        },
        mode="create",
    )


@shop_admin_bp.route(
    "/admin/urunler/<int:product_id>/duzenle",
    methods=["GET", "POST"],
)
@login_required
def product_edit(product_id):
    _require_shop_admin()

    product = db.session.get(
        Product,
        product_id,
    )

    if product is None:
        abort(404)

    if request.method == "POST":
        _validate_csrf()

        payload = _form_payload()

        validated = _validate_product_form(
            payload,
            current_product_id=product.id,
        )

        if validated["errors"]:
            for error in validated["errors"]:
                flash(error, "error")

            return render_template(
                "admin_product_form.html",
                product=product,
                form=payload,
                mode="edit",
            ), 400

        _apply_product_data(
            product,
            payload,
            validated,
        )

        db.session.commit()

        flash(
            "Ürün güncellendi.",
            "success",
        )

        return redirect(
            url_for(
                "shop_admin.product_list"
            )
        )

    form = {
        "name": product.name or "",
        "slug": product.slug or "",
        "category": product.category or "",
        "price": str(
            product.price
            if product.price is not None
            else ""
        ),
        "stock": str(
            product.stock
            if product.stock is not None
            else 0
        ),
        "short_description": (
            product.short_description or ""
        ),
        "description": (
            product.description or ""
        ),
        "image_url": (
            product.image_url or ""
        ),
        "shopier_product_id": (
            product.shopier_product_id or ""
        ),
        "shopier_url": (
            product.shopier_url or ""
        ),
        "is_active": bool(
            product.is_active
        ),
        "is_featured": bool(
            product.is_featured
        ),
    }

    return render_template(
        "admin_product_form.html",
        product=product,
        form=form,
        mode="edit",
    )


@shop_admin_bp.post(
    "/admin/urunler/<int:product_id>/durum"
)
@login_required
def product_toggle(product_id):
    _require_shop_admin()
    _validate_csrf()

    product = db.session.get(
        Product,
        product_id,
    )

    if product is None:
        abort(404)

    product.is_active = (
        not bool(product.is_active)
    )

    db.session.commit()

    flash(
        (
            "Ürün yayına alındı."
            if product.is_active
            else "Ürün mağazadan gizlendi."
        ),
        "success",
    )

    return redirect(
        url_for(
            "shop_admin.product_list"
        )
    )
