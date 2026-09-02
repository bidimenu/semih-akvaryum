import json
import os
from urllib.parse import quote, urlparse

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from extensions import db, login_manager
from models import (
    Aquarium,
    AquariumChatMessage,
    AquariumPlanRevision,
    User,
)
from services.gemini_service import (
    AquariumPlan,
    AquariumPlanGenerationError,
    ask_aquarium_advisor,
    generate_aquarium_plan,
    stream_aquarium_advisor,
    revise_aquarium_plan,
)

from services.analysis_service import (
    AquariumAnalysis,
    AquariumAnalysisGenerationError,
    generate_aquarium_analysis,
    stream_analysis_advisor,
)

from services.compatibility_service import (
    CompatibilityGenerationError,
    generate_compatibility_result,
)


load_dotenv()

app = Flask(__name__)

# Danışmanlık V1
# Shopier ürün linkini ve WhatsApp numaranı Render Environment'tan gir.
app.config["SHOPIER_CONSULTING_URL"] = os.getenv(
    "SHOPIER_CONSULTING_URL",
    "",
).strip()

app.config["CONSULTING_WHATSAPP_NUMBER"] = os.getenv(
    "CONSULTING_WHATSAPP_NUMBER",
    "",
).strip()


app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "dev-only-change-this-before-production",
)

database_url = os.getenv(
    "DATABASE_URL",
    "",
).strip()

# Render Postgres connectionString değeri postgresql:// ile gelir.
# Psycopg 3 sürücüsünü açıkça seçerek ortamlar arası sürücü farkını kaldırıyoruz.
if database_url.startswith(
    "postgresql://"
):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )

if not database_url:
    database_url = (
        "sqlite:///semih_akvaryum.db"
    )

app.config[
    "SQLALCHEMY_DATABASE_URI"
] = database_url

app.config[
    "SQLALCHEMY_TRACK_MODIFICATIONS"
] = False

app.config[
    "SQLALCHEMY_ENGINE_OPTIONS"
] = {
    "pool_pre_ping": True,
}

# Fotoğraf dahil tüm form isteği için güvenli üst sınır.
app.config[
    "MAX_CONTENT_LENGTH"
] = 10 * 1024 * 1024

is_production = (
    os.getenv(
        "PRODUCTION",
        "",
    ).strip()
    == "1"
)

app.config[
    "SESSION_COOKIE_HTTPONLY"
] = True

app.config[
    "SESSION_COOKIE_SAMESITE"
] = "Lax"

app.config[
    "SESSION_COOKIE_SECURE"
] = is_production

app.config[
    "REMEMBER_COOKIE_HTTPONLY"
] = True

app.config[
    "REMEMBER_COOKIE_SAMESITE"
] = "Lax"

app.config[
    "REMEMBER_COOKIE_SECURE"
] = is_production

app.config[
    "PREFERRED_URL_SCHEME"
] = (
    "https"
    if is_production
    else "http"
)

db.init_app(app)
login_manager.init_app(app)

# V1 deployment:
# Yeni PostgreSQL veritabanında mevcut tabloları otomatik oluşturur.
# İlk gerçek schema değişikliğinden önce Flask-Migrate/Alembic'e geçeceğiz.
with app.app_context():
    db.create_all()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "semih-akvaryum",
    }, 200


@app.route("/")
def home():
    return render_template("index.html")


def _shopier_consulting_url():
    """
    Sadece Shopier domainine yönlendirmeye izin ver.
    Environment yanlış ayarlanırsa açık redirect oluşmasın.
    """
    value = app.config.get(
        "SHOPIER_CONSULTING_URL",
        "",
    ).strip()

    if not value:
        return None

    try:
        parsed = urlparse(value)

    except ValueError:
        return None

    host = (
        parsed.hostname
        or ""
    ).lower()

    if (
        parsed.scheme not in {
            "http",
            "https",
        }
        or not (
            host == "shopier.com"
            or host.endswith(".shopier.com")
        )
    ):
        return None

    return value


def _consulting_whatsapp_number():
    """
    wa.me yalnızca ülke koduyla birlikte rakam bekler.
    Örn: 90555XXXXXXX
    """
    raw = app.config.get(
        "CONSULTING_WHATSAPP_NUMBER",
        "",
    )

    digits = "".join(
        char
        for char in raw
        if char.isdigit()
    )

    if len(digits) < 10:
        return None

    return digits


@app.get("/danismanlik")
def consulting():
    return render_template(
        "danismanlik.html",
        shopier_ready=bool(
            _shopier_consulting_url()
        ),
        whatsapp_ready=bool(
            _consulting_whatsapp_number()
        ),
    )


@app.get("/danismanlik/satin-al")
def consulting_buy():
    shopier_url = (
        _shopier_consulting_url()
    )

    if not shopier_url:
        flash(
            "Shopier ödeme bağlantısı henüz tanımlanmadı.",
            "error",
        )

        return redirect(
            url_for("consulting")
        )

    return redirect(
        shopier_url,
        code=302,
    )


@app.get("/danismanlik/whatsapp")
def consulting_whatsapp():
    issue = request.args.get(
        "issue",
        "Genel danışmanlık",
    ).strip()

    allowed_issues = {
        "Balık sağlığı / problem",
        "Yeni akvaryum kurulumu",
        "Bitkili akvaryum",
        "Ürün / ekipman önerisi",
        "Canlı seçimi / uyumu",
        "Mevcut tankı geliştirme",
        "Genel danışmanlık",
    }

    if issue not in allowed_issues:
        issue = "Genel danışmanlık"

    phone = _consulting_whatsapp_number()

    if not phone:
        flash(
            "WhatsApp danışmanlık numarası henüz tanımlanmadı.",
            "error",
        )

        return redirect(
            url_for("consulting")
        )

    message = (
        "Merhaba Semih, "
        "1 Aylık Akvaryum Danışmanlığı paketini "
        "Shopier üzerinden satın aldım.\n\n"
        f"Danışmanlık Konusu: {issue}\n\n"
        "Danışmanlığımı başlatmak istiyorum."
    )

    whatsapp_url = (
        f"https://wa.me/{phone}"
        f"?text={quote(message, safe='')}"
    )

    return redirect(
        whatsapp_url,
        code=302,
    )


@app.route("/uye-ol", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("aquariums"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        errors = []

        if len(username) < 3:
            errors.append(
                "Kullanıcı adı en az 3 karakter olmalı."
            )

        if len(username) > 40:
            errors.append(
                "Kullanıcı adı en fazla 40 karakter olabilir."
            )

        if "@" not in email or "." not in email:
            errors.append(
                "Geçerli bir e-posta adresi gir."
            )

        if len(password) < 8:
            errors.append(
                "Şifren en az 8 karakter olmalı."
            )

        if password != password_confirm:
            errors.append(
                "Şifreler birbiriyle eşleşmiyor."
            )

        existing_username = db.session.scalar(
            db.select(User).where(
                func.lower(User.username) == username.lower()
            )
        )

        if existing_username:
            errors.append(
                "Bu kullanıcı adı zaten kullanılıyor."
            )

        existing_email = db.session.scalar(
            db.select(User).where(
                func.lower(User.email) == email
            )
        )

        if existing_email:
            errors.append(
                "Bu e-posta adresiyle zaten bir hesap var."
            )

        if errors:
            for error in errors:
                flash(error, "error")

            return render_template(
                "register.html",
                username=username,
                email=email,
            ), 400

        user = User(
            username=username,
            email=email,
        )

        user.set_password(password)

        db.session.add(user)

        try:
            db.session.commit()

        except IntegrityError:
            db.session.rollback()

            flash(
                "Bu kullanıcı adı veya e-posta zaten kullanılıyor.",
                "error",
            )

            return render_template(
                "register.html",
                username=username,
                email=email,
            ), 409

        login_user(user)

        flash(
            "Hesabın oluşturuldu. Hoş geldin!",
            "success",
        )

        return redirect(
            url_for("aquariums")
        )

    return render_template(
        "register.html",
        username="",
        email="",
    )


@app.route("/giris", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("aquariums"))

    if request.method == "POST":
        login_value = request.form.get(
            "login",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        remember = (
            request.form.get("remember")
            == "1"
        )

        user = db.session.scalar(
            db.select(User).where(
                or_(
                    func.lower(User.email)
                    == login_value.lower(),

                    func.lower(User.username)
                    == login_value.lower(),
                )
            )
        )

        if (
            user is None
            or not user.check_password(password)
        ):
            flash(
                "Kullanıcı adı/e-posta veya şifre hatalı.",
                "error",
            )

            return render_template(
                "login.html",
                login_value=login_value,
            ), 401

        login_user(
            user,
            remember=remember,
        )

        flash(
            f"Tekrar hoş geldin, {user.username}.",
            "success",
        )

        return redirect(
            url_for("aquariums")
        )

    return render_template(
        "login.html",
        login_value="",
    )


@app.post("/cikis")
@login_required
def logout():
    logout_user()

    flash(
        "Hesabından çıkış yaptın.",
        "info",
    )

    return redirect(
        url_for("home")
    )


@app.route("/akvaryumlarim")
@login_required
def aquariums():
    user_aquariums = db.session.scalars(
        db.select(Aquarium)
        .where(
            Aquarium.user_id == current_user.id
        )
        .order_by(
            Aquarium.created_at.desc()
        )
    ).all()

    return render_template(
        "aquariums.html",
        aquariums=user_aquariums,
    )


def get_owned_aquarium_or_404(aquarium_id):
    aquarium = db.session.get(
        Aquarium,
        aquarium_id,
    )

    if aquarium is None:
        abort(404)

    if aquarium.user_id != current_user.id:
        abort(403)

    return aquarium


@app.route(
    "/akvaryum/<int:aquarium_id>"
)
@login_required
def aquarium_detail(aquarium_id):
    aquarium = get_owned_aquarium_or_404(
        aquarium_id
    )

    plan = None

    if aquarium.plan_json:
        try:
            plan = AquariumPlan.model_validate_json(
                aquarium.plan_json
            )
        except ValidationError:
            plan = None

    chat_messages = db.session.scalars(
        db.select(AquariumChatMessage)
        .where(
            AquariumChatMessage.aquarium_id
            == aquarium.id
        )
        .order_by(
            AquariumChatMessage.created_at.asc()
        )
    ).all()

    revision_count = db.session.scalar(
        db.select(
            func.count(AquariumPlanRevision.id)
        )
        .where(
            AquariumPlanRevision.aquarium_id
            == aquarium.id
        )
    ) or 0

    return render_template(
        "aquarium_detail.html",
        aquarium=aquarium,
        plan=plan,
        chat_messages=chat_messages,
        revision_count=revision_count,
    )




@app.post(
    "/akvaryum/<int:aquarium_id>/ai-stream"
)
@login_required
def stream_tank_ai(aquarium_id):
    aquarium = get_owned_aquarium_or_404(aquarium_id)

    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()

    if len(question) < 2:
        return {
            "error": "AI'ya sormak istediğin soruyu yaz."
        }, 400

    if len(question) > 1200:
        return {
            "error": "Soruyu 1200 karakterden kısa tutalım."
        }, 400

    try:
        plan = AquariumPlan.model_validate_json(
            aquarium.plan_json or ""
        )
    except ValidationError:
        return {
            "error": (
                "Bu tankın AI planı okunamadığı için "
                "soru gönderilemiyor."
            )
        }, 400

    recent_messages = db.session.scalars(
        db.select(AquariumChatMessage)
        .where(
            AquariumChatMessage.aquarium_id
            == aquarium.id
        )
        .order_by(
            AquariumChatMessage.created_at.desc()
        )
        .limit(6)
    ).all()

    history = [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in reversed(recent_messages)
    ]

    tank_id = aquarium.id

    @stream_with_context
    def generate():
        answer_parts = []

        try:
            yield "event: ready\ndata: {}\n\n"

            for text in stream_aquarium_advisor(
                plan=plan,
                question=question,
                history=history,
            ):
                answer_parts.append(text)

                payload_text = json.dumps(
                    {"text": text},
                    ensure_ascii=False,
                )

                yield (
                    "event: delta\n"
                    f"data: {payload_text}\n\n"
                )

            full_answer = "".join(answer_parts).strip()

            if not full_answer:
                raise AquariumPlanGenerationError(
                    "Gemini boş yanıt döndürdü."
                )

            db.session.add_all(
                [
                    AquariumChatMessage(
                        aquarium_id=tank_id,
                        role="user",
                        content=question,
                    ),
                    AquariumChatMessage(
                        aquarium_id=tank_id,
                        role="assistant",
                        content=full_answer,
                    ),
                ]
            )
            db.session.commit()

            yield (
                "event: done\n"
                'data: {"saved": true}\n\n'
            )

        except AquariumPlanGenerationError as exc:
            db.session.rollback()

            error_data = json.dumps(
                {"message": str(exc)},
                ensure_ascii=False,
            )

            yield (
                "event: error\n"
                f"data: {error_data}\n\n"
            )

        except Exception as exc:
            db.session.rollback()

            error_data = json.dumps(
                {
                    "message": (
                        "AI yanıtı alınırken beklenmeyen "
                        "bir hata oluştu: "
                        + str(exc)[:250]
                    )
                },
                ensure_ascii=False,
            )

            yield (
                "event: error\n"
                f"data: {error_data}\n\n"
            )

    response = Response(
        generate(),
        mimetype="text/event-stream",
    )

    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"

    return response


@app.post(
    "/akvaryum/<int:aquarium_id>/ai-sor"
)
@login_required
def ask_tank_ai(aquarium_id):
    aquarium = get_owned_aquarium_or_404(
        aquarium_id
    )

    question = request.form.get(
        "question",
        "",
    ).strip()

    if len(question) < 2:
        flash(
            "AI'ya sormak istediğin soruyu yaz.",
            "error",
        )

        return redirect(
            url_for(
                "aquarium_detail",
                aquarium_id=aquarium.id,
            )
            + "#tank-ai"
        )

    if len(question) > 1200:
        flash(
            "Soruyu 1200 karakterden kısa tutalım.",
            "error",
        )

        return redirect(
            url_for(
                "aquarium_detail",
                aquarium_id=aquarium.id,
            )
            + "#tank-ai"
        )

    try:
        plan = AquariumPlan.model_validate_json(
            aquarium.plan_json or ""
        )

    except ValidationError:
        flash(
            "Bu tankın AI planı okunamadığı için soru gönderilemiyor.",
            "error",
        )

        return redirect(
            url_for(
                "aquarium_detail",
                aquarium_id=aquarium.id,
            )
        )

    recent_messages = db.session.scalars(
        db.select(AquariumChatMessage)
        .where(
            AquariumChatMessage.aquarium_id
            == aquarium.id
        )
        .order_by(
            AquariumChatMessage.created_at.desc()
        )
        .limit(8)
    ).all()

    history = [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in reversed(recent_messages)
    ]

    try:
        answer = ask_aquarium_advisor(
            plan=plan,
            question=question,
            history=history,
        )

    except AquariumPlanGenerationError as exc:
        flash(
            str(exc),
            "error",
        )

        return redirect(
            url_for(
                "aquarium_detail",
                aquarium_id=aquarium.id,
            )
            + "#tank-ai"
        )

    user_message = AquariumChatMessage(
        aquarium_id=aquarium.id,
        role="user",
        content=question,
    )

    assistant_message = AquariumChatMessage(
        aquarium_id=aquarium.id,
        role="assistant",
        content=answer,
    )

    db.session.add_all(
        [
            user_message,
            assistant_message,
        ]
    )

    db.session.commit()

    return redirect(
        url_for(
            "aquarium_detail",
            aquarium_id=aquarium.id,
        )
        + "#tank-ai"
    )


@app.post(
    "/akvaryum/<int:aquarium_id>/revize-et"
)
@login_required
def revise_tank_plan(aquarium_id):
    aquarium = get_owned_aquarium_or_404(
        aquarium_id
    )

    instruction = request.form.get(
        "instruction",
        "",
    ).strip()

    if len(instruction) < 5:
        flash(
            "Planı nasıl değiştirmek istediğini biraz daha açık yaz.",
            "error",
        )

        return redirect(
            url_for(
                "aquarium_detail",
                aquarium_id=aquarium.id,
            )
            + "#plan-revision"
        )

    if len(instruction) > 1200:
        flash(
            "Revizyon talebini 1200 karakterden kısa tutalım.",
            "error",
        )

        return redirect(
            url_for(
                "aquarium_detail",
                aquarium_id=aquarium.id,
            )
            + "#plan-revision"
        )

    try:
        current_plan = AquariumPlan.model_validate_json(
            aquarium.plan_json or ""
        )

    except ValidationError:
        flash(
            "Mevcut plan okunamadığı için revize edilemiyor.",
            "error",
        )

        return redirect(
            url_for(
                "aquarium_detail",
                aquarium_id=aquarium.id,
            )
        )

    try:
        revised_plan = revise_aquarium_plan(
            current_plan=current_plan,
            instruction=instruction,
        )

    except AquariumPlanGenerationError as exc:
        flash(
            str(exc),
            "error",
        )

        return redirect(
            url_for(
                "aquarium_detail",
                aquarium_id=aquarium.id,
            )
            + "#plan-revision"
        )

    revision = AquariumPlanRevision(
        aquarium_id=aquarium.id,
        instruction=instruction,
        previous_plan_json=aquarium.plan_json,
    )

    aquarium.plan_json = (
        revised_plan.model_dump_json()
    )

    aquarium.title = revised_plan.title
    aquarium.subtitle = revised_plan.subtitle
    aquarium.gross_volume_liters = (
        revised_plan.gross_volume_liters
    )
    aquarium.style = revised_plan.design_style
    aquarium.fit_score = revised_plan.fit_score

    aquarium.livestock_summary = ", ".join(
        [
            f"{item.quantity} {item.common_name}"
            for item in revised_plan.livestock[:4]
        ]
    )

    db.session.add(revision)
    db.session.commit()

    flash(
        "Plan AI tarafından güncellendi. Önceki sürüm geçmişte saklandı.",
        "success",
    )

    return redirect(
        url_for(
            "aquarium_detail",
            aquarium_id=aquarium.id,
        )
        + "#plan-revision"
    )


@app.post(
    "/akvaryum/<int:aquarium_id>/sil"
)
@login_required
def delete_aquarium(aquarium_id):
    aquarium = get_owned_aquarium_or_404(
        aquarium_id
    )

    tank_title = aquarium.title

    db.session.delete(aquarium)
    db.session.commit()

    flash(
        f"{tank_title} profilinden silindi.",
        "info",
    )

    return redirect(
        url_for("aquariums")
    )


@app.post("/akvaryum-kaydet")
@login_required
def save_aquarium():
    plan_json = request.form.get(
        "plan_json",
        "",
    )

    form_json = request.form.get(
        "form_json",
        "",
    )

    if not plan_json:
        flash(
            "Kaydedilecek akvaryum planı bulunamadı.",
            "error",
        )

        return redirect(
            url_for("akvaryum_kur")
        )

    try:
        plan = AquariumPlan.model_validate_json(
            plan_json
        )

        form_data = (
            json.loads(form_json)
            if form_json
            else {}
        )

    except (
        ValidationError,
        json.JSONDecodeError,
    ):
        flash(
            "Akvaryum planı doğrulanamadı. Lütfen planı yeniden oluştur.",
            "error",
        )

        return redirect(
            url_for("akvaryum_kur")
        )

    # Aynı kullanıcının tamamen aynı AI planını yanlışlıkla
    # art arda kaydetmesini engelliyoruz.
    existing = db.session.scalar(
        db.select(Aquarium).where(
            Aquarium.user_id == current_user.id,
            Aquarium.plan_json == plan_json,
        )
    )

    if existing:
        flash(
            "Bu akvaryum zaten profilinde kayıtlı.",
            "info",
        )

        return redirect(
            url_for(
                "aquarium_detail",
                aquarium_id=existing.id,
            )
        )

    def safe_float(value):
        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

    livestock_summary = ", ".join(
        [
            f"{item.quantity} {item.common_name}"
            for item in plan.livestock[:4]
        ]
    )

    aquarium = Aquarium(
        user_id=current_user.id,

        title=plan.title,
        subtitle=plan.subtitle,

        length_cm=safe_float(
            form_data.get("length")
        ),

        width_cm=safe_float(
            form_data.get("width")
        ),

        height_cm=safe_float(
            form_data.get("height")
        ),

        gross_volume_liters=plan.gross_volume_liters,

        style=plan.design_style,

        livestock_summary=livestock_summary,

        fit_score=plan.fit_score,

        plan_json=plan_json,
    )

    db.session.add(aquarium)
    db.session.commit()

    flash(
        "Akvaryum profilinde kaydedildi.",
        "success",
    )

    return redirect(
        url_for(
            "aquarium_detail",
            aquarium_id=aquarium.id,
        )
    )





@app.route(
    "/canli-uyumu",
    methods=["GET", "POST"],
)
def canli_uyumu():

    if request.method == "GET":
        return render_template(
            "canli_uyumu.html",
            form_data={},
            api_error=None,
        )

    form_data = {
        "length": request.form.get(
            "length",
            "",
        ).strip(),

        "width": request.form.get(
            "width",
            "",
        ).strip(),

        "height": request.form.get(
            "height",
            "",
        ).strip(),

        "temperature": request.form.get(
            "temperature",
            "",
        ).strip(),

        "ph": request.form.get(
            "ph",
            "",
        ).strip(),

        "current_livestock": request.form.get(
            "current_livestock",
            "",
        ).strip(),

        "filtration": request.form.get(
            "filtration",
            "",
        ).strip(),

        "water_notes": request.form.get(
            "water_notes",
            "",
        ).strip(),

        "candidate": request.form.get(
            "candidate",
            "",
        ).strip(),

        "candidate_quantity": request.form.get(
            "candidate_quantity",
            "",
        ).strip(),

        "notes": request.form.get(
            "notes",
            "",
        ).strip(),
    }

    required_fields = {
        "length": "Uzunluk",
        "width": "Genişlik",
        "height": "Yükseklik",
        "current_livestock": "Mevcut canlılar",
        "candidate": "Eklemek istediğin canlı",
        "candidate_quantity": "Eklemek istediğin adet",
    }

    missing = [
        label
        for field, label
        in required_fields.items()
        if not form_data[field]
    ]

    if missing:
        return render_template(
            "canli_uyumu.html",
            form_data=form_data,
            api_error=(
                "Bazı bilgiler eksik görünüyor: "
                + ", ".join(missing)
            ),
        ), 400

    try:
        length = float(
            form_data["length"]
        )

        width = float(
            form_data["width"]
        )

        height = float(
            form_data["height"]
        )

        quantity = int(
            form_data[
                "candidate_quantity"
            ]
        )

        if (
            length <= 0
            or width <= 0
            or height <= 0
            or quantity <= 0
        ):
            raise ValueError

    except ValueError:
        return render_template(
            "canli_uyumu.html",
            form_data=form_data,
            api_error=(
                "Tank ölçüleri ve canlı adedi "
                "pozitif sayı olmalı."
            ),
        ), 400

    gross_volume = round(
        (
            length
            * width
            * height
        )
        / 1000,
        1,
    )

    # Backend hesapladığı litreyi modele de veriyoruz.
    form_data["gross_volume_liters"] = (
        gross_volume
    )

    try:
        result = (
            generate_compatibility_result(
                form_data
            )
        )

        return render_template(
            "canli_uyumu_sonuc.html",
            result=result,
            form_data=form_data,
            gross_volume=gross_volume,
        )

    except CompatibilityGenerationError as exc:
        return render_template(
            "canli_uyumu.html",
            form_data=form_data,
            api_error=str(exc),
        ), 502


@app.post(
    "/akvaryum-analiz/chat-stream"
)
def stream_analysis_chat():

    payload = request.get_json(
        silent=True
    ) or {}

    question = str(
        payload.get(
            "question",
            "",
        )
    ).strip()

    if len(question) < 2:
        return {
            "error": (
                "AI'ya sormak istediğin soruyu yaz."
            )
        }, 400

    if len(question) > 1200:
        return {
            "error": (
                "Soruyu 1200 karakterden kısa tutalım."
            )
        }, 400

    try:
        analysis = (
            AquariumAnalysis
            .model_validate(
                payload.get(
                    "analysis",
                    {},
                )
            )
        )

    except ValidationError:
        return {
            "error": (
                "Analiz bağlamı doğrulanamadı. "
                "Lütfen analizi yeniden oluştur."
            )
        }, 400

    form_data = payload.get(
        "form_data",
        {},
    )

    if not isinstance(
        form_data,
        dict,
    ):
        form_data = {}

    raw_history = payload.get(
        "history",
        [],
    )

    if not isinstance(
        raw_history,
        list,
    ):
        raw_history = []

    history = []

    for item in raw_history[-6:]:

        if not isinstance(
            item,
            dict,
        ):
            continue

        role = str(
            item.get(
                "role",
                "",
            )
        )

        content = str(
            item.get(
                "content",
                "",
            )
        ).strip()

        if (
            role
            in {
                "user",
                "assistant",
            }
            and content
        ):
            history.append(
                {
                    "role": role,
                    "content": (
                        content[:3000]
                    ),
                }
            )

    @stream_with_context
    def generate():

        try:

            yield (
                "event: ready\n"
                "data: {}\n\n"
            )

            for text in (
                stream_analysis_advisor(
                    analysis=analysis,
                    form_data=form_data,
                    question=question,
                    history=history,
                )
            ):

                data = json.dumps(
                    {
                        "text": text,
                    },
                    ensure_ascii=False,
                )

                yield (
                    "event: delta\n"
                    f"data: {data}\n\n"
                )

            yield (
                "event: done\n"
                'data: {"done": true}\n\n'
            )

        except (
            AquariumAnalysisGenerationError
        ) as exc:

            error_data = json.dumps(
                {
                    "message": str(exc),
                },
                ensure_ascii=False,
            )

            yield (
                "event: error\n"
                f"data: {error_data}\n\n"
            )

        except Exception as exc:

            error_data = json.dumps(
                {
                    "message": (
                        "AI yanıtı alınırken "
                        "beklenmeyen bir hata oluştu: "
                        + str(exc)[:250]
                    ),
                },
                ensure_ascii=False,
            )

            yield (
                "event: error\n"
                f"data: {error_data}\n\n"
            )

    response = Response(
        generate(),
        mimetype="text/event-stream",
    )

    response.headers[
        "Cache-Control"
    ] = "no-cache, no-transform"

    response.headers[
        "X-Accel-Buffering"
    ] = "no"

    response.headers[
        "Connection"
    ] = "keep-alive"

    return response


@app.route(
    "/akvaryum-analiz",
    methods=["GET", "POST"],
)
def akvaryum_analiz():

    if request.method == "GET":
        return render_template(
            "akvaryum_analiz.html",
            form_data={},
            api_error=None,
        )

    form_data = {
        "length": request.form.get(
            "length",
            "",
        ).strip(),

        "width": request.form.get(
            "width",
            "",
        ).strip(),

        "height": request.form.get(
            "height",
            "",
        ).strip(),

        "livestock": request.form.get(
            "livestock",
            "",
        ).strip(),

        "plants": request.form.get(
            "plants",
            "",
        ).strip(),

        "filter": request.form.get(
            "filter",
            "",
        ).strip(),

        "lighting": request.form.get(
            "lighting",
            "",
        ).strip(),

        "co2": request.form.get(
            "co2",
            "",
        ).strip(),

        "water_change": request.form.get(
            "water_change",
            "",
        ).strip(),

        "water_values": request.form.get(
            "water_values",
            "",
        ).strip(),

        "description": request.form.get(
            "description",
            "",
        ).strip(),
    }

    required_fields = {
        "length": "Uzunluk",
        "width": "Genişlik",
        "height": "Yükseklik",
        "livestock": "Canlılar",
        "filter": "Filtre",
        "lighting": "Işık",
        "co2": "CO₂",
        "water_change": "Su değişimi",
        "description": "Analiz notu",
    }

    missing = [
        label
        for field, label
        in required_fields.items()
        if not form_data[field]
    ]

    if missing:
        return render_template(
            "akvaryum_analiz.html",
            form_data=form_data,
            api_error=(
                "Bazı bilgiler eksik görünüyor: "
                + ", ".join(missing)
            ),
        ), 400

    image_file = request.files.get(
        "aquarium_photo"
    )

    image_bytes = None
    image_mime_type = None

    if (
        image_file
        and image_file.filename
    ):
        allowed_mime_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
        }

        image_mime_type = (
            image_file.mimetype
            or ""
        ).lower()

        if (
            image_mime_type
            not in allowed_mime_types
        ):
            return render_template(
                "akvaryum_analiz.html",
                form_data=form_data,
                api_error=(
                    "Fotoğraf formatı desteklenmiyor. "
                    "JPG, PNG veya WEBP kullan."
                ),
            ), 400

        image_bytes = image_file.read()

        if len(image_bytes) > 8 * 1024 * 1024:
            return render_template(
                "akvaryum_analiz.html",
                form_data=form_data,
                api_error=(
                    "Fotoğraf en fazla 8 MB olabilir."
                ),
            ), 400

        if not image_bytes:
            image_bytes = None
            image_mime_type = None

    try:
        result = generate_aquarium_analysis(
            form_data=form_data,
            image_bytes=image_bytes,
            image_mime_type=image_mime_type,
        )

        try:
            gross_volume = (
                float(form_data["length"])
                * float(form_data["width"])
                * float(form_data["height"])
            ) / 1000

            gross_volume = round(
                gross_volume,
                1,
            )

        except (
            TypeError,
            ValueError,
        ):
            gross_volume = None

        return render_template(
            "akvaryum_analiz_sonuc.html",
            result=result,
            form_data=form_data,
            gross_volume=gross_volume,
            photo_used=bool(image_bytes),

            # Chat V1 browser içinde bu iki context'i kullanır.
            # Veritabanına kaydetmiyoruz.
            analysis_payload=result.model_dump(),
            form_payload=form_data,
        )

    except AquariumAnalysisGenerationError as exc:
        return render_template(
            "akvaryum_analiz.html",
            form_data=form_data,
            api_error=str(exc),
        ), 502


@app.route(
    "/akvaryum-kur",
    methods=["GET", "POST"],
)
def akvaryum_kur():
    if request.method == "GET":
        return render_template(
            "akvaryum_kur.html",
            submitted=False,
            api_error=None,
        )

    form_data = {
        "length": request.form.get("length", "").strip(),
        "width": request.form.get("width", "").strip(),
        "height": request.form.get("height", "").strip(),
        "budget": request.form.get("budget", "").strip(),
        "experience": request.form.get("experience", "").strip(),
        "maintenance": request.form.get("maintenance", "").strip(),
        "style": request.form.get("style", "").strip(),
        "co2": request.form.get("co2", "").strip(),
        "livestock": request.form.get("livestock", "").strip(),
        "dream": request.form.get("dream", "").strip(),
    }

    required_fields = {
        "length": "Uzunluk",
        "width": "Genişlik",
        "height": "Yükseklik",
        "budget": "Bütçe",
        "experience": "Deneyim",
        "maintenance": "Bakım",
        "style": "Tarz",
        "co2": "CO₂",
        "livestock": "Canlı",
        "dream": "Hayal",
    }

    missing = [
        label
        for field, label
        in required_fields.items()
        if not form_data[field]
    ]

    if missing:
        return render_template(
            "akvaryum_kur.html",
            submitted=False,
            api_error=(
                "Bazı bilgiler eksik görünüyor: "
                + ", ".join(missing)
            ),
        ), 400

    try:
        plan = generate_aquarium_plan(
            form_data
        )

        return render_template(
            "akvaryum_sonuc.html",
            plan=plan,
            form_data=form_data,

            # Template'te hidden input'a güvenli biçimde
            # taşımak için JSON string hazırlıyoruz.
            plan_json=plan.model_dump_json(),
            form_json=json.dumps(
                form_data,
                ensure_ascii=False,
            ),
        )

    except AquariumPlanGenerationError as exc:
        return render_template(
            "akvaryum_kur.html",
            submitted=False,
            api_error=str(exc),
        ), 502


if __name__ == "__main__":
    app.run(debug=True)
