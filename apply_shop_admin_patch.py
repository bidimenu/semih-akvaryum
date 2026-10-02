from pathlib import Path
import shutil
import sys


ROOT = Path.cwd()

APP = ROOT / "app.py"
MODELS = ROOT / "models.py"
TEMPLATES = ROOT / "templates"
CSS = ROOT / "static" / "css"


def fail(message):
    print(f"\nHATA: {message}")
    sys.exit(1)


if not APP.exists():
    fail("app.py bulunamadı. Scripti proje root klasöründe çalıştır.")

if not MODELS.exists():
    fail("models.py bulunamadı.")

models_text = MODELS.read_text(
    encoding="utf-8"
)

if "class Product(" not in models_text:
    fail(
        "Product modeli bulunamadı. Önce Mağaza V1 paketini uygula."
    )

source_dir = Path(__file__).resolve().parent

TEMPLATES.mkdir(
    parents=True,
    exist_ok=True,
)

CSS.mkdir(
    parents=True,
    exist_ok=True,
)

shutil.copy2(
    source_dir / "shop_admin.py",
    ROOT / "shop_admin.py",
)

shutil.copy2(
    source_dir / "templates" / "admin_products.html",
    TEMPLATES / "admin_products.html",
)

shutil.copy2(
    source_dir / "templates" / "admin_product_form.html",
    TEMPLATES / "admin_product_form.html",
)

shutil.copy2(
    source_dir / "static" / "css" / "shop_admin.css",
    CSS / "shop_admin.css",
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
            "app.py içinde extensions import satırı bulunamadı."
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
            "app.py içinde login_manager.init_app(app) bulunamadı."
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

print("\nMağaza Admin V2 başarıyla uygulandı.")
print("")
print("Şimdi .env içine şunu ekle:")
print("SHOP_ADMIN_EMAIL=senin-site-hesabi-emailin")
print("")
print("Ardından:")
print("python app.py")
print("")
print("Admin:")
print("http://127.0.0.1:5000/admin/urunler")
