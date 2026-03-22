"""
Flask application factory for Postgres Learning Studio Web UI.
Serves the benchmark configuration, execution, and results UI
directly from the SPCS container.
"""

import os

from flask import Flask, make_response, redirect, request

from i18n import get_lang, t


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32).hex()

    # i18n context processor
    @app.context_processor
    def inject_i18n():
        return {"t": t, "lang": get_lang()}

    # Language toggle route
    @app.route("/lang/<code>")
    def set_lang(code):
        if code not in ("en", "ja"):
            code = "en"
        resp = make_response(redirect(request.referrer or "/"))
        resp.set_cookie("lang", code, max_age=60 * 60 * 24 * 365)
        return resp

    # Register blueprints
    from web.routes.benchmark import benchmark_bp
    from web.routes.compare import compare_bp
    from web.routes.health import health_bp
    from web.routes.index import index_bp
    from web.routes.results import results_bp
    from web.routes.sql_client import sql_bp
    from web.routes.system import system_bp
    from web.routes.scripts import scripts_bp
    from web.routes.targets import targets_bp
    from web.routes.advanced import advanced_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(index_bp)
    app.register_blueprint(benchmark_bp)
    app.register_blueprint(results_bp)
    app.register_blueprint(compare_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(sql_bp)
    app.register_blueprint(targets_bp)
    app.register_blueprint(scripts_bp)
    app.register_blueprint(advanced_bp)

    # Prevent browsers from caching HTML after Compute Pool suspend/resume
    @app.after_request
    def set_cache_headers(response):
        if response.content_type and "text/html" in response.content_type:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    return app
