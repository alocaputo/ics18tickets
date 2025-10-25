import requests
import json
import ics
import os
import yaml
from datetime import datetime, timedelta
from typing import Optional


def get_existing_calendar(file_path: str) -> ics.Calendar:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            calendar = ics.Calendar(f.read())
    else:
        calendar = ics.Calendar()
    return calendar


CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.yml')


def _load_default_films_url() -> str:
    """Return the films API URL constructed from `config.yml` if present.

    The function requires a valid `config.yml` with a `site` entry. If the file is
    missing or invalid this function raises a RuntimeError so the caller fails loudly.
    """
    cfg = _load_config(require_site=True)
    site = cfg.get('site')
    api_path = cfg.get('api_path', '/api/v2/films')
    scheme = cfg.get('scheme', 'https')
    site = str(site).strip().rstrip('/')
    if site.startswith('http://') or site.startswith('https://'):
        base = site
    else:
        base = f"{scheme}://{site}"

    return f"{base.rstrip('/')}{api_path}"


def _load_config(require_site: bool = True) -> dict:
    """Load and return the parsed `config.yml` as a dict.

    If `require_site` is True the function will raise a RuntimeError when `site` is
    missing. The function always raises on missing file or YAML parse errors.
    """
    if not os.path.exists(CONFIG_FILE):
        raise RuntimeError(
            f"Configuration file not found: {CONFIG_FILE}. Please create it and set 'site', e.g.\n"
            "site: example.18tickets.it\n"
        )

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        try:
            cfg = yaml.safe_load(f) or {}
        except Exception as exc:
            raise RuntimeError(f"Failed to parse {CONFIG_FILE}: {exc}") from exc

    if require_site and not cfg.get('site'):
        raise RuntimeError(
            f"'site' not set in {CONFIG_FILE}. Please set the target host, e.g.\n"
            "site: example.18tickets.it\n"
        )

    return cfg


def fetch_films_json(url: Optional[str] = None) -> dict:
    if url is None:
        url = _load_default_films_url()
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def create_ics_event(uid: str, title: str, start_time: str, duration: int, description: str, location: Optional[str] = None) -> ics.Event:
    event = ics.Event()
    event.name = title
    event.begin = datetime.fromisoformat(start_time)
    event.end = event.begin + timedelta(minutes=duration)
    event.description = description
    event.location = location
    event.uid = uid
    event.created = datetime.now()
    event.last_modified = datetime.now()
    return event


def generate_ics(output_path: str = "ics18tickets.ics") -> bool:
    """Fetch films and write `output_path`. Returns True if calendar was modified/written.

    This function is safe to call repeatedly; it will skip events whose UID already
    exists in the existing calendar file.
    """
    cal = get_existing_calendar(output_path)
    existing_events = {event.uid: event for event in cal.events}

    # Read URL from config.yml (fetch_films_json will raise if config is missing/invalid)
    json_data = fetch_films_json()

    # Read the configured address (optional) to use as event location
    # Load configured address if present; if not present leave it as None so we
    # do not set a location on the ICS event.
    cfg = None
    try:
        cfg = _load_config(require_site=True)
    except RuntimeError:
        # _load_config already raises if config missing/invalid; if it does,
        # we continue with configured_address = None so caller can handle it.
        cfg = None
    configured_address = None if cfg is None else cfg.get('address')

    calendar_was_modified = False

    for film in json_data.get('films', []):
        title = film.get('title')
        plot = film.get('plot')
        duration = film.get('length', 0)
        film_url = film.get('film_url')
        film_occupations = film.get('film_occupations', [])

        print(f"Title: {title}")
        for occupation in film_occupations:
            start = occupation.get('start')
            theater_name = occupation.get('theater_name')
            public_id = occupation.get('public_id')

            if public_id in existing_events:
                print(f"  Skipping existing event: {title} at {start}")
                continue
            else:
                event = create_ics_event(
                    uid=str(public_id),
                    title=(title or "").capitalize(),
                    start_time=start,
                    duration=duration,
                    description=f"{theater_name}\n\n{plot}\n\nMore info: {film_url}",
                    # If `address` is configured, use it; otherwise leave `location` None
                    # (the create_ics_event will accept Optional[str]).
                    location=(configured_address if configured_address else None)
                )
                cal.events.add(event)
                print(f"  Added event: {title} at {start}")
                calendar_was_modified = True

    if calendar_was_modified:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cal.serialize())
        print(f"Wrote calendar to {output_path}")
    else:
        print("No changes detected; calendar not updated.")

    return calendar_was_modified


if __name__ == '__main__':
    # keep the previous behavior when running the script directly
    generate_ics()