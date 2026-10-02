
from pathlib import Path
import sys

ROOT = Path.cwd()
APP = ROOT / "app.py"
MODELS = ROOT / "models.py"
TEMPLATES = ROOT / "templates"
CSS_DIR = ROOT / "static" / "css"


SHOP_ADMIN_PY = r"""import hmac
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
"""


ADMIN_PRODUCTS_HTML = r"""{% extends "base.html" %}

{% block title %}
Ürün Yönetimi · Semih Akvaryum
{% endblock %}

{% block extra_css %}
<link
    rel="stylesheet"
    href="{{ url_for('static', filename='css/shop_admin.css', v='20261003-2') }}"
>
{% endblock %}

{% block content %}

<section class="shop-admin-page">
    <div class="shop-admin-shell">

        <header class="shop-admin-header">
            <div>
                <span class="shop-admin-eyebrow">
                    SEMİH.AKVARYUM · ADMIN
                </span>

                <h1>Ürün Yönetimi</h1>

                <p>
                    Mağazadaki ürünleri ekle, fiyat ve stok bilgisini güncelle.
                </p>
            </div>

            <a
                href="{{ url_for('shop_admin.product_create') }}"
                class="shop-admin-primary"
            >
                + Yeni ürün
            </a>
        </header>

        <div class="shop-admin-top-links">
            <a href="{{ url_for('shop') }}">
                ← Mağazaya git
            </a>
        </div>

        {% if products %}
            <div class="shop-admin-list">
                {% for product in products %}
                    <article class="shop-admin-product">

                        <div class="shop-admin-image">
                            {% if product.image_url %}
                                <img
                                    src="{{ product.image_url }}"
                                    alt="{{ product.name }}"
                                >
                            {% else %}
                                <span>SA</span>
                            {% endif %}
                        </div>

                        <div class="shop-admin-product-main">

                            <div class="shop-admin-product-top">
                                <div>
                                    <small>
                                        {{ product.category or "Kategorisiz" }}
                                    </small>

                                    <h2>
                                        {{ product.name }}
                                    </h2>
                                </div>

                                <span
                                    class="shop-admin-status {% if product.is_active %}is-live{% else %}is-hidden{% endif %}"
                                >
                                    {% if product.is_active %}
                                        Yayında
                                    {% else %}
                                        Gizli
                                    {% endif %}
                                </span>
                            </div>

                            <div class="shop-admin-metrics">
                                <div>
                                    <small>FİYAT</small>
                                    <strong>
                                        {{ product.display_price }} TL
                                    </strong>
                                </div>

                                <div>
                                    <small>STOK</small>
                                    <strong>
                                        {{ product.stock }}
                                    </strong>
                                </div>

                                <div>
                                    <small>SHOPIER ID</small>
                                    <strong>
                                        {{ product.shopier_product_id or "—" }}
                                    </strong>
                                </div>
                            </div>

                            <div class="shop-admin-actions">

                                <a
                                    href="{{ url_for(
                                        'product_detail',
                                        slug=product.slug
                                    ) }}"
                                    target="_blank"
                                >
                                    Ürünü gör ↗
                                </a>

                                <a
                                    href="{{ url_for(
                                        'shop_admin.product_edit',
                                        product_id=product.id
                                    ) }}"
                                    class="edit"
                                >
                                    Düzenle
                                </a>

                                <form
                                    method="POST"
                                    action="{{ url_for(
                                        'shop_admin.product_toggle',
                                        product_id=product.id
                                    ) }}"
                                >
                                    <input
                                        type="hidden"
                                        name="csrf_token"
                                        value="{{ shop_admin_csrf_token() }}"
                                    >

                                    <button type="submit">
                                        {% if product.is_active %}
                                            Mağazadan gizle
                                        {% else %}
                                            Yayına al
                                        {% endif %}
                                    </button>
                                </form>

                            </div>
                        </div>
                    </article>
                {% endfor %}
            </div>

        {% else %}
            <div class="shop-admin-empty">
                <span>◎</span>
                <h2>Henüz ürün yok.</h2>
                <p>
                    İlk Semih Akvaryum ürününü ekleyerek başlayalım.
                </p>

                <a
                    href="{{ url_for('shop_admin.product_create') }}"
                    class="shop-admin-primary"
                >
                    İlk ürünü ekle
                </a>
            </div>
        {% endif %}

    </div>
</section>

{% endblock %}
"""


ADMIN_FORM_HTML = r"""{% extends "base.html" %}

{% block title %}
{% if mode == "create" %}Yeni Ürün{% else %}Ürün Düzenle{% endif %} · Semih Akvaryum
{% endblock %}

{% block extra_css %}
<link
    rel="stylesheet"
    href="{{ url_for('static', filename='css/shop_admin.css', v='20261003-2') }}"
>
{% endblock %}

{% block content %}

<section class="shop-admin-page">

    <div class="shop-admin-shell shop-admin-form-shell">

        <a
            href="{{ url_for('shop_admin.product_list') }}"
            class="shop-admin-back"
        >
            ← Ürün yönetimine dön
        </a>

        <header class="shop-admin-form-header">

            <span class="shop-admin-eyebrow">
                SEMİH.AKVARYUM · STORE
            </span>

            <h1>
                {% if mode == "create" %}
                    Yeni ürün ekle
                {% else %}
                    Ürünü düzenle
                {% endif %}
            </h1>

            <p>
                Shopier'deki ürün bilgileriyle aynı olacak şekilde doldur.
            </p>

        </header>

        <form
            method="POST"
            class="shop-admin-form"
        >

            <input
                type="hidden"
                name="csrf_token"
                value="{{ shop_admin_csrf_token() }}"
            >

            <div class="shop-admin-form-grid">

                <label class="shop-admin-field shop-admin-field-wide">
                    <span>Ürün adı *</span>

                    <input
                        type="text"
                        name="name"
                        value="{{ form.name }}"
                        maxlength="220"
                        required
                        placeholder="Örn. WaterBear SD-01 Pipo Filtre"
                    >
                </label>

                <label class="shop-admin-field">
                    <span>Slug</span>

                    <input
                        type="text"
                        name="slug"
                        value="{{ form.slug }}"
                        maxlength="160"
                        placeholder="Boş bırakırsan otomatik oluşur"
                    >

                    <small>
                        semihakvaryum.com/urun/...
                    </small>
                </label>

                <label class="shop-admin-field">
                    <span>Kategori</span>

                    <input
                        type="text"
                        name="category"
                        value="{{ form.category }}"
                        maxlength="100"
                        placeholder="Filtre, Bitki, Dekor..."
                    >
                </label>

                <label class="shop-admin-field">
                    <span>Fiyat (TL) *</span>

                    <input
                        type="text"
                        name="price"
                        value="{{ form.price }}"
                        inputmode="decimal"
                        required
                        placeholder="349,90"
                    >
                </label>

                <label class="shop-admin-field">
                    <span>Stok *</span>

                    <input
                        type="number"
                        name="stock"
                        value="{{ form.stock }}"
                        min="0"
                        step="1"
                        required
                    >
                </label>

                <label class="shop-admin-field shop-admin-field-wide">
                    <span>Kısa açıklama</span>

                    <textarea
                        name="short_description"
                        maxlength="500"
                        rows="3"
                        placeholder="Ürün kartında görünecek kısa açıklama."
                    >{{ form.short_description }}</textarea>
                </label>

                <label class="shop-admin-field shop-admin-field-wide">
                    <span>Uzun açıklama</span>

                    <textarea
                        name="description"
                        rows="9"
                        placeholder="Ürün detay sayfasında görünecek açıklama."
                    >{{ form.description }}</textarea>
                </label>

                <label class="shop-admin-field shop-admin-field-wide">
                    <span>Ürün görsel URL'si</span>

                    <input
                        type="url"
                        name="image_url"
                        value="{{ form.image_url }}"
                        placeholder="https://..."
                    >
                </label>

                <label class="shop-admin-field">
                    <span>Shopier Product ID</span>

                    <input
                        type="text"
                        name="shopier_product_id"
                        value="{{ form.shopier_product_id }}"
                        maxlength="100"
                        placeholder="Örn. 50488190"
                    >
                </label>

                <label class="shop-admin-field">
                    <span>Shopier satın alma linki *</span>

                    <input
                        type="url"
                        name="shopier_url"
                        value="{{ form.shopier_url }}"
                        required
                        placeholder="https://www.shopier.com/..."
                    >
                </label>

            </div>

            <div class="shop-admin-switches">

                <label>
                    <input
                        type="checkbox"
                        name="is_active"
                        value="1"
                        {% if form.is_active %}checked{% endif %}
                    >

                    <span>
                        <strong>Mağazada yayınla</strong>
                        <small>
                            Kapalıysa ürün ziyaretçilere görünmez.
                        </small>
                    </span>
                </label>

                <label>
                    <input
                        type="checkbox"
                        name="is_featured"
                        value="1"
                        {% if form.is_featured %}checked{% endif %}
                    >

                    <span>
                        <strong>Önerilen ürün</strong>
                        <small>
                            Mağazada önce gösterilir.
                        </small>
                    </span>
                </label>

            </div>

            <div class="shop-admin-form-actions">

                <a
                    href="{{ url_for('shop_admin.product_list') }}"
                >
                    Vazgeç
                </a>

                <button type="submit">
                    {% if mode == "create" %}
                        Ürünü ekle
                    {% else %}
                        Değişiklikleri kaydet
                    {% endif %}
                </button>

            </div>

        </form>

    </div>

</section>

{% endblock %}
"""


SHOP_ADMIN_CSS = r""".shop-admin-page {
    min-height: calc(100vh - 76px);
    padding: 72px 0 120px;
    color: #ecf7f6;
    background:
        radial-gradient(circle at 12% 5%, rgba(58, 211, 192, .08), transparent 28%),
        #061112;
}

.shop-admin-shell {
    width: min(1120px, calc(100% - 36px));
    margin: 0 auto;
}

.shop-admin-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 28px;
    margin-bottom: 25px;
}

.shop-admin-eyebrow {
    display: block;
    margin-bottom: 10px;
    color: #63dacb;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 2.1px;
}

.shop-admin-header h1,
.shop-admin-form-header h1 {
    margin: 0;
    font-family: "Manrope", sans-serif;
    font-size: clamp(34px, 5vw, 54px);
    line-height: 1;
    letter-spacing: -2.4px;
}

.shop-admin-header p,
.shop-admin-form-header p {
    margin: 14px 0 0;
    color: #829a98;
    line-height: 1.6;
}

.shop-admin-primary {
    display: inline-flex;
    min-height: 48px;
    align-items: center;
    justify-content: center;
    padding: 0 18px;
    border-radius: 14px;
    color: #041311;
    background: #66dccc;
    font-size: 12px;
    font-weight: 900;
    text-decoration: none;
}

.shop-admin-top-links {
    margin-bottom: 28px;
}

.shop-admin-top-links a,
.shop-admin-back {
    color: #789491;
    font-size: 12px;
    font-weight: 700;
    text-decoration: none;
}

.shop-admin-list {
    display: grid;
    gap: 13px;
}

.shop-admin-product {
    display: grid;
    grid-template-columns: 126px minmax(0, 1fr);
    overflow: hidden;
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 20px;
    background: rgba(255,255,255,.032);
}

.shop-admin-image {
    display: grid;
    min-height: 145px;
    place-items: center;
    overflow: hidden;
    color: #53716e;
    font-size: 14px;
    font-weight: 900;
    background: #0a1918;
}

.shop-admin-image img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.shop-admin-product-main {
    padding: 20px 22px;
}

.shop-admin-product-top {
    display: flex;
    justify-content: space-between;
    gap: 20px;
}

.shop-admin-product-top small {
    color: #5ccfbf;
    font-size: 9px;
    font-weight: 900;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}

.shop-admin-product-top h2 {
    margin: 5px 0 0;
    font-size: 18px;
}

.shop-admin-status {
    height: fit-content;
    padding: 7px 10px;
    border-radius: 999px;
    font-size: 9px;
    font-weight: 900;
}

.shop-admin-status.is-live {
    color: #65d7a1;
    background: rgba(65,200,139,.08);
}

.shop-admin-status.is-hidden {
    color: #a4aaa9;
    background: rgba(255,255,255,.05);
}

.shop-admin-metrics {
    display: flex;
    gap: 42px;
    margin-top: 21px;
}

.shop-admin-metrics small,
.shop-admin-metrics strong {
    display: block;
}

.shop-admin-metrics small {
    color: #55706d;
    font-size: 8px;
    font-weight: 900;
    letter-spacing: 1.2px;
}

.shop-admin-metrics strong {
    margin-top: 4px;
    color: #e9f5f4;
    font-size: 13px;
}

.shop-admin-actions {
    display: flex;
    align-items: center;
    gap: 9px;
    margin-top: 18px;
}

.shop-admin-actions a,
.shop-admin-actions button {
    min-height: 34px;
    padding: 0 11px;
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 10px;
    color: #8da7a4;
    background: rgba(255,255,255,.025);
    font-family: inherit;
    font-size: 10px;
    font-weight: 800;
    text-decoration: none;
    cursor: pointer;
}

.shop-admin-actions a.edit {
    color: #74dfd1;
}

.shop-admin-empty {
    padding: 90px 24px;
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 22px;
    text-align: center;
    background: rgba(255,255,255,.025);
}

.shop-admin-empty > span {
    color: #63d8c9;
    font-size: 42px;
}

.shop-admin-empty h2 {
    margin: 15px 0 5px;
}

.shop-admin-empty p {
    margin: 0 0 24px;
    color: #78918e;
}

.shop-admin-form-shell {
    max-width: 920px;
}

.shop-admin-form-header {
    margin-top: 32px;
    margin-bottom: 32px;
}

.shop-admin-form {
    padding: 26px;
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 24px;
    background: rgba(255,255,255,.027);
}

.shop-admin-form-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
}

.shop-admin-field {
    display: block;
}

.shop-admin-field-wide {
    grid-column: 1 / -1;
}

.shop-admin-field > span {
    display: block;
    margin-bottom: 7px;
    color: #a4b9b6;
    font-size: 11px;
    font-weight: 800;
}

.shop-admin-field input,
.shop-admin-field textarea {
    box-sizing: border-box;
    width: 100%;
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 13px;
    outline: none;
    padding: 13px 14px;
    color: #f0f8f7;
    background: #081817;
    font-family: inherit;
}

.shop-admin-field textarea {
    resize: vertical;
    line-height: 1.6;
}

.shop-admin-field input:focus,
.shop-admin-field textarea:focus {
    border-color: rgba(93,218,203,.46);
}

.shop-admin-field small {
    display: block;
    margin-top: 6px;
    color: #55706d;
    font-size: 9px;
}

.shop-admin-switches {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    margin-top: 24px;
}

.shop-admin-switches label {
    display: flex;
    gap: 11px;
    align-items: flex-start;
    padding: 15px;
    border: 1px solid rgba(255,255,255,.06);
    border-radius: 14px;
    background: rgba(255,255,255,.02);
}

.shop-admin-switches input {
    margin-top: 2px;
}

.shop-admin-switches strong,
.shop-admin-switches small {
    display: block;
}

.shop-admin-switches strong {
    color: #dce9e7;
    font-size: 11px;
}

.shop-admin-switches small {
    margin-top: 3px;
    color: #66807d;
    font-size: 9px;
    line-height: 1.4;
}

.shop-admin-form-actions {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 10px;
    margin-top: 28px;
    padding-top: 22px;
    border-top: 1px solid rgba(255,255,255,.06);
}

.shop-admin-form-actions a {
    padding: 12px 14px;
    color: #78918e;
    font-size: 11px;
    font-weight: 800;
    text-decoration: none;
}

.shop-admin-form-actions button {
    min-height: 46px;
    padding: 0 18px;
    border: 0;
    border-radius: 13px;
    color: #051311;
    background: #65dbcc;
    font-family: inherit;
    font-size: 11px;
    font-weight: 900;
    cursor: pointer;
}

@media (max-width: 700px) {
    .shop-admin-page {
        padding: 48px 0 80px;
    }

    .shop-admin-header {
        align-items: stretch;
        flex-direction: column;
    }

    .shop-admin-primary {
        width: 100%;
    }

    .shop-admin-product {
        grid-template-columns: 90px minmax(0, 1fr);
    }

    .shop-admin-image {
        min-height: 100%;
    }

    .shop-admin-product-main {
        padding: 16px;
    }

    .shop-admin-metrics {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 13px;
    }

    .shop-admin-actions {
        flex-wrap: wrap;
    }

    .shop-admin-form {
        padding: 17px;
    }

    .shop-admin-form-grid,
    .shop-admin-switches {
        grid-template-columns: 1fr;
    }

    .shop-admin-field-wide {
        grid-column: auto;
    }
}
"""


def fail(message):
    print(f"\nHATA: {message}")
    sys.exit(1)


if not APP.exists():
    fail(
        "app.py bulunamadı. Bu dosyayı semih-akvaryum proje klasörüne koyup orada çalıştır."
    )

if not MODELS.exists():
    fail("models.py bulunamadı.")

models_text = MODELS.read_text(
    encoding="utf-8"
)

if "class Product(" not in models_text:
    fail(
        "models.py içinde Product modeli yok. Önce Mağaza V1'in çalıştığını kontrol et."
    )

TEMPLATES.mkdir(
    parents=True,
    exist_ok=True,
)

CSS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

(ROOT / "shop_admin.py").write_text(
    SHOP_ADMIN_PY,
    encoding="utf-8",
)

(TEMPLATES / "admin_products.html").write_text(
    ADMIN_PRODUCTS_HTML,
    encoding="utf-8",
)

(TEMPLATES / "admin_product_form.html").write_text(
    ADMIN_FORM_HTML,
    encoding="utf-8",
)

(CSS_DIR / "shop_admin.css").write_text(
    SHOP_ADMIN_CSS,
    encoding="utf-8",
)

app_text = APP.read_text(
    encoding="utf-8"
)

import_line = (
    "from shop_admin import shop_admin_bp"
)

if import_line not in app_text:
    marker = "from extensions import db, login_manager"

    if marker not in app_text:
        fail(
            "app.py içinde 'from extensions import db, login_manager' bulunamadı."
        )

    app_text = app_text.replace(
        marker,
        marker + "\n" + import_line,
        1,
    )

register_line = (
    "app.register_blueprint(shop_admin_bp)"
)

if register_line not in app_text:
    marker = "login_manager.init_app(app)"

    if marker not in app_text:
        fail(
            "app.py içinde 'login_manager.init_app(app)' bulunamadı."
        )

    app_text = app_text.replace(
        marker,
        marker + "\n" + register_line,
        1,
    )

APP.write_text(
    app_text,
    encoding="utf-8",
)

print("")
print("========================================")
print(" SEMİH AKVARYUM SHOP ADMIN V2.1 HAZIR ")
print("========================================")
print("")
print("Oluşturulan/güncellenen dosyalar:")
print("- shop_admin.py")
print("- templates/admin_products.html")
print("- templates/admin_product_form.html")
print("- static/css/shop_admin.css")
print("- app.py (blueprint bağlandı)")
print("")
print("Şimdi .env içine:")
print("")
print("SHOP_ADMIN_EMAIL=site-hesabinda-kullandigin-email")
print("")
print("Sonra:")
print("python app.py")
print("")
print("Giriş yaptıktan sonra:")
print("http://127.0.0.1:5000/admin/urunler")
print("")
