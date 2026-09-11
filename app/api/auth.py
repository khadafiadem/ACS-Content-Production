from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse

from app.services import tiktok_auth

router = APIRouter(prefix="/auth/tiktok", tags=["tiktok-auth"])


@router.get("/login")
async def tiktok_login():
    """Redirect user ke TikTok OAuth authorize page."""
    if not tiktok_auth.client_configured():
        return RedirectResponse("/?tiktok=notconfigured", status_code=303)
    auth_url = tiktok_auth.build_authorize_url()
    return RedirectResponse(auth_url)


@router.get("/callback")
async def tiktok_callback(request: Request):
    """Callback dari TikTok setelah user approve (code di query)."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    if error:
        return JSONResponse({"success": False, "error": f"TikTok menolak: {error}"}, status_code=400)
    if not code:
        return JSONResponse({"success": False, "error": "Kode OAuth tidak ada"}, status_code=400)

    result = await tiktok_auth.exchange_code(code, state)
    if result.get("success"):
        return RedirectResponse("/?tiktok=connected", status_code=303)
    return JSONResponse({"success": False, "error": result.get("error")}, status_code=400)


@router.get("/status")
async def tiktok_status():
    return tiktok_auth.store_status()


@router.post("/refresh")
async def tiktok_refresh():
    result = await tiktok_auth.refresh_access_token()
    if not result.get("success"):
        return JSONResponse(result, status_code=400)
    return {"success": True}


@router.post("/logout")
async def tiktok_logout():
    """Hapus token tersimpan."""
    import os
    try:
        os.remove(tiktok_auth._store_path())
    except FileNotFoundError:
        pass
    return {"success": True}