from __future__ import annotations

import logging
import logging.handlers

from telegram import BotCommand
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters

from app.ai.receipt_extractor import DummyReceiptExtractor, LlamaCppReceiptExtractor
from app.ai.ocr import PaddleOCREngine
from app.ai.glm_ocr import LlamaCppOCREngine
from app.ai.voice_transcriber import VoiceTranscriber
from app.bot.handlers import BotHandlers
from app.config import get_settings
from app.db.database import init_db, init_engine
from app.db.repositories import TransactionRepository
from app.services.report_service import ReportService
from app.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand("start", "Mulai bot"),
    BotCommand("help", "Panduan penggunaan"),
    BotCommand("laporan_hari_ini", "Lihat laporan pengeluaran hari ini"),
    BotCommand("laporan_bulan_ini", "Lihat laporan pengeluaran bulan ini"),
    BotCommand("transaksi_terakhir", "Lihat transaksi terbaru"),
    BotCommand("rekap", "Buat laporan harian (PDF)"),
    BotCommand("batal", "Batalkan input total manual"),
    BotCommand("status", "Cek status server AI"),
]


async def _post_init(application: Application) -> None:
    try:
        await application.bot.set_my_commands(BOT_COMMANDS)
        logger.info("Telegram bot commands registered")
    except Exception:
        logger.exception("Failed to register Telegram bot commands")

    # Health check AI servers at startup
    from app.utils.health import check_all_services

    settings = get_settings()
    if settings.enable_startup_health_check:
        results = await check_all_services(settings.llamacpp_base_url, settings.whisper_server_base_url)
        for service, healthy in results.items():
            if not healthy:
                logger.warning("⚠️  %s server is NOT reachable at startup", service)


def build_application() -> Application:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN belum diatur.")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_engine(settings.database_url)
    init_db()

    if settings.use_dummy_extractor or settings.extractor_backend == "dummy":
        extractor = DummyReceiptExtractor()
    else:
        extractor = LlamaCppReceiptExtractor(
            base_url=settings.llamacpp_base_url,
            model=settings.llamacpp_model,
            timeout_seconds=settings.request_timeout_seconds,
        )

    repository = TransactionRepository()
    transaction_service = TransactionService(repository, settings.timezone)
    report_service = ReportService(repository)
    voice_transcriber = VoiceTranscriber(
        base_url=settings.whisper_server_base_url,
        inference_path=settings.whisper_server_inference_path,
        timeout_seconds=settings.whisper_server_timeout_seconds,
        language=settings.whisper_language,
    )
    ocr_engine = None
    if settings.ocr_backend == "vlm_llamacpp":
        ocr_engine = None  # VLM: extractor handles image directly
    elif settings.ocr_backend == "glm_ocr_llamacpp":
        ocr_engine = LlamaCppOCREngine(
            base_url=settings.glm_ocr_base_url,
            model=settings.glm_ocr_model,
            prompt=settings.glm_ocr_prompt,
            timeout_seconds=settings.glm_ocr_timeout_seconds,
            max_tokens=settings.glm_ocr_max_tokens,
        )
    elif settings.ocr_backend == "paddleocr":
        ocr_engine = PaddleOCREngine(lang=settings.ocr_language)
    else:
        logger.warning("Unknown OCR_BACKEND=%r, falling back to PaddleOCR", settings.ocr_backend)
        ocr_engine = PaddleOCREngine(lang=settings.ocr_language)

    handlers = BotHandlers(
        transaction_service=transaction_service,
        report_service=report_service,
        extractor=extractor,
        voice_transcriber=voice_transcriber,
        upload_dir=settings.upload_dir,
        ocr_engine=ocr_engine,
        timezone=settings.timezone,
        allowed_user_ids=settings.allowed_user_ids,
        enable_user_whitelist=settings.enable_user_whitelist,
    )

    async def _post_shutdown(application: Application) -> None:
        aclose = getattr(extractor, "aclose", None)
        if aclose is not None:
            await aclose()

    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help))
    application.add_handler(CommandHandler("laporan_hari_ini", handlers.laporan_hari_ini))
    application.add_handler(CommandHandler("laporan_bulan_ini", handlers.laporan_bulan_ini))
    application.add_handler(CommandHandler("transaksi_terakhir", handlers.transaksi_terakhir))
    application.add_handler(CommandHandler("rekap", handlers.rekap_command))
    application.add_handler(CommandHandler("batal", handlers.batal_pending_total))
    application.add_handler(CommandHandler("status", handlers.status))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handlers.handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handlers.handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_pending_total_text))
    return application


def run() -> None:
    from pathlib import Path

    log_file = Path(__file__).resolve().parent.parent / "bot.log"
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),
            logging.handlers.RotatingFileHandler(
                log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
            ),
        ],
    )
    app = build_application()
    logger.info("Bot starting...")
    app.run_polling()
