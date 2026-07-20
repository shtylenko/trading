"""Read-mostly FastAPI UI for the YT Explorer SQLite ledger."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from ..store import CANDIDATE_STATUSES, CHANNEL_STATUSES, ExplorerStore


WEB_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def create_app(db_path: Path | str | None = None) -> FastAPI:
    store = ExplorerStore(db_path)
    store.init()
    app = FastAPI(title="YT Explorer", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    def render(request: Request, name: str, **context):
        return TEMPLATES.TemplateResponse(request, name, {"nav": request.url.path, **context})

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        stats = store.dashboard()
        return render(request, "dashboard.html", stats=stats, candidates=store.list_candidates()[:8], videos=store.list_videos(limit=6))

    @app.get("/inbox", response_class=HTMLResponse)
    def inbox(request: Request, status: Optional[str] = None):
        return render(request, "inbox.html", videos=store.list_videos(status=status, limit=250), selected_status=status)

    @app.get("/videos/{video_id}", response_class=HTMLResponse)
    def video_detail(request: Request, video_id: str):
        video = store.get_video(video_id)
        if video is None:
            raise HTTPException(404, "unknown video")
        return render(request, "video_detail.html", video=video, claims=store.claims_for_video(video_id),
                      extractions=store.extractions_for_video(video_id))

    @app.get("/channels", response_class=HTMLResponse)
    def channels(request: Request, status: Optional[str] = None):
        return render(request, "channels.html", channels=store.list_channels(status=status), selected_status=status)

    @app.get("/channels/{channel_id}", response_class=HTMLResponse)
    def channel_detail(request: Request, channel_id: str):
        channel = store.get_channel(channel_id)
        if channel is None:
            raise HTTPException(404, "unknown channel")
        videos = [v for v in store.list_videos(limit=1000) if v["channel_id"] == channel_id]
        return render(request, "channel_detail.html", channel=channel, videos=videos, statuses=sorted(CHANNEL_STATUSES))

    @app.post("/channels/{channel_id}/status")
    def update_channel_status(channel_id: str, status: str = Form(...), reason: str = Form("")):
        channel = store.get_channel(channel_id)
        if channel is None:
            raise HTTPException(404, "unknown channel")
        store.update_channel_audit(
            channel_id, sample_size=channel["audit_sample_size"],
            trading_ratio=channel["trading_ratio"] or 0, strategy_ratio=channel["strategy_ratio"] or 0,
            status=status, reason=reason or channel["audit_reason"] or "manually updated in web UI",
        )
        return RedirectResponse(f"/channels/{channel_id}", status_code=303)

    @app.get("/claims", response_class=HTMLResponse)
    def claims(request: Request):
        return render(request, "claims.html", claims=store.list_claims())

    @app.get("/candidates", response_class=HTMLResponse)
    def candidates(request: Request, status: Optional[str] = None):
        return render(request, "candidates.html", candidates=store.list_candidates(status=status), selected_status=status,
                      statuses=sorted(CANDIDATE_STATUSES))

    @app.get("/candidates/{candidate_id}", response_class=HTMLResponse)
    def candidate_detail(request: Request, candidate_id: str):
        candidate = store.get_candidate(candidate_id)
        if candidate is None:
            raise HTTPException(404, "unknown candidate")
        return render(
            request, "candidate_detail.html", candidate=candidate, statuses=sorted(CANDIDATE_STATUSES),
            events=store.candidate_events(candidate_id), experiments=store.experiment_links(candidate_id),
        )

    @app.post("/candidates/{candidate_id}/transition")
    def transition(candidate_id: str, status: str = Form(...), rationale: str = Form("")):
        try:
            store.transition_candidate(candidate_id, status, actor="web", rationale=rationale)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return RedirectResponse(f"/candidates/{candidate_id}", status_code=303)

    @app.get("/experiments", response_class=HTMLResponse)
    def experiments(request: Request):
        return render(request, "experiments.html", experiments=store.experiment_links())

    @app.get("/search-plan", response_class=HTMLResponse)
    def search_plan(request: Request):
        from ..pipeline import DEFAULT_PLAN_PATH, load_plan
        plan = load_plan()
        return render(request, "search_plan.html", plan=plan, plan_path=DEFAULT_PLAN_PATH)

    @app.get("/operations", response_class=HTMLResponse)
    def operations(request: Request):
        run = store.latest_pipeline_run()
        return render(request, "operations.html", stats=store.dashboard(), db_path=store.path, run=run,
                      runs=store.list_pipeline_runs(),
                      events=store.pipeline_events(run["run_id"]) if run else [])

    @app.get("/operations/{run_id}", response_class=HTMLResponse)
    def operation_detail(request: Request, run_id: str):
        run = store.get_pipeline_run(run_id)
        if run is None:
            raise HTTPException(404, "unknown pipeline run")
        decorated = next((item for item in store.list_pipeline_runs(limit=1000) if item["run_id"] == run_id), run)
        return render(request, "operation_detail.html", run=decorated, events=store.pipeline_events(run_id, limit=500))

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "database": str(store.path), **store.dashboard()}

    return app


app = create_app()


def main() -> None:
    import uvicorn
    uvicorn.run("trading.ytexplorer.web.app:app", host="127.0.0.1", port=8791, reload=True)


if __name__ == "__main__":
    main()
