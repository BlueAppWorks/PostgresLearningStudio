"""
Postgres Learning Studio - Main entry point.
Starts Flask Web UI on port 8080.
All benchmark operations run directly via Flask routes against PostgreSQL.
"""

if __name__ == "__main__":
    print("=== Postgres Learning Studio ===")

    from web.app import create_app

    app = create_app()

    print("Starting Flask Web UI on :8080")
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
