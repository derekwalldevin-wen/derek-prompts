#!/usr/bin/env python3
"""一条命令产出「国内可部署包 + 二维码 + 双站互链 + 本地验收」。

    python tools/deploy_cn.py                                # 默认子域名 derek-prompts.edgeone.app
    python tools/deploy_cn.py --url https://xxx.edgeone.app  # 换成实际拿到的域名
    python tools/deploy_cn.py --skip-test                    # 只打包、跑测试

步骤：
  1. 重建 docs/    —— GitHub 版，页脚链到国内镜像
  2. 重建 dist-cn/ —— 国内版，canonical/og 指向国内域名，页脚链回 GitHub
  3. 打包 德里克文提示词库-国内部署包.zip
  4. 生成 share/qr-国内.png 与 qr-github.png（二维码 + 地址，可直接放图里）
  5. 用 dist-cn 起本地服务，跑 verify + e2e + 老内核降级测试
"""
from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
GH = "https://derekwalldevin-wen.github.io/derek-prompts"
DEFAULT_CN = "https://derek-prompts.edgeone.app"
DIST = ROOT / "dist-cn"
ZIP_BASE = ROOT / "德里克文提示词库-国内部署包"
SHARE = ROOT / "share"


def node_bin() -> str:
    for cand in (
        shutil.which("node"),
        r"C:\Users\derek\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe",
    ):
        if cand and Path(cand).exists():
            return cand
    raise SystemExit("找不到 node，可加 --skip-test")


def run(cmd: list[str], cwd: Path) -> None:
    print("$", " ".join(str(c) for c in cmd))
    if subprocess.run([str(c) for c in cmd], cwd=str(cwd)).returncode != 0:
        raise SystemExit(f"命令失败: {' '.join(str(c) for c in cmd)}")


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_qr(url: str, out: Path, title: str = "扫码打开 · 德里克文提示词库") -> Path:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1612", back_color="#fffdf8").convert("RGB")

    pad, top, bottom = 48, 36, 40
    canvas = Image.new("RGB", (img.width + pad * 2, img.height + top + bottom + 92), "#fffdf8")
    canvas.paste(img, (pad, top))
    d = ImageDraw.Draw(canvas)
    try:
        f_big = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 34)
        f_small = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 23)
    except Exception:  # noqa: BLE001
        f_big = f_small = ImageFont.load_default()

    y = top + img.height + 16
    d.text(((canvas.width - d.textlength(title, font=f_big)) / 2, y), title, fill="#1a1612", font=f_big)
    disp = url.replace("https://", "").rstrip("/")
    d.text(((canvas.width - d.textlength(disp, font=f_small)) / 2, y + 46), disp, fill="#6e655a", font=f_small)

    out.parent.mkdir(exist_ok=True)
    canvas.save(out, "PNG")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_CN, help="国内版域名")
    ap.add_argument("--skip-test", action="store_true")
    a = ap.parse_args()
    url = a.url.rstrip("/")

    run([sys.executable, "build.py", "--base", GH, "--mirror", url], ROOT / "site")
    run([sys.executable, "build.py", "--out", str(DIST), "--base", url, "--mirror", GH], ROOT / "site")

    for old in (ZIP_BASE.with_suffix(".zip"),):
        old.unlink(missing_ok=True)
    shutil.make_archive(str(ZIP_BASE), "zip", DIST)

    qr_cn = make_qr(url, SHARE / "qr-国内.png")
    qr_gh = make_qr(GH, SHARE / "qr-github.png", "扫码打开 · GitHub 版")

    data = json.loads((ROOT / "data" / "prompts.json").read_text(encoding="utf-8"))
    files = [f for f in DIST.rglob("*") if f.is_file()]
    mb = sum(f.stat().st_size for f in files) / 1048576

    print("\n" + "=" * 64)
    print(f"国内版  : {url}")
    print(f"GitHub  : {GH}")
    print(f"部署包  : {ZIP_BASE.name}.zip  ({mb:.1f} MB / {len(files)} 文件)")
    print(f"二维码  : {qr_cn.name} / {qr_gh.name}")
    print(f"条目    : {len(data)} 条")
    print("=" * 64)

    if a.skip_test:
        return

    port = free_port()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "-d", str(DIST)],
                           cwd=str(DIST), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f"http://127.0.0.1:{port}/"
        for _ in range(40):
            try:
                with urllib.request.urlopen(base, timeout=2) as r:
                    if r.status == 200:
                        break
            except Exception:  # noqa: BLE001
                time.sleep(0.25)
        run([sys.executable, "verify.py"], ROOT / "site")
        run([node_bin(), "tools/e2e.mjs", "--url", base], ROOT)
        run([node_bin(), "tools/check-fallback.mjs", "--url", base], ROOT)
        print("\n✅ 本地验收全部通过（verify + 22 项功能 + 老内核降级）")
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except Exception:  # noqa: BLE001
            srv.kill()

    print("\n下一步：解压 zip，把 dist-cn 文件夹拖到 https://pages.edgeone.ai/zh/drop ，"
          f"子域名填 {url.split('//')[-1].split('.')[0]}")


if __name__ == "__main__":
    main()
