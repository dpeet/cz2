# src/pycz2/__main__.py
import typer
import uvicorn

from . import cli
from .config import settings

app = typer.Typer(
    name="pycz2",
    help="A Python tool to control Carrier ComfortZone II HVAC systems.",
    add_completion=False,
)

app.add_typer(cli.app, name="cli")


@app.command()
def api_server():
    """
    Runs the FastAPI web server and MQTT background task.
    """
    print(
        f"Starting pycz2 API server on http://{settings.API_HOST}:{settings.API_PORT}"
    )
    print("Interactive API docs available at http://localhost:8000/docs")
    if settings.MQTT_ENABLED:
        print(
            f"MQTT publisher enabled. Publishing to "
            f"'{settings.MQTT_TOPIC_PREFIX}/status' "
            f"every {settings.MQTT_PUBLISH_INTERVAL}s."
        )
    else:
        print("MQTT publisher is disabled.")

    uvicorn.run(
        "pycz2.api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,  # Set to True for development
    )


# For convenience, alias 'api' to 'api_server'
app.command("api")(api_server)


if __name__ == "__main__":
    app()
