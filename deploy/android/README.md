# Chạy md2x trên Android (đã root)

## Vì sao cài `uv` cứ lỗi

`uv` không phát hành bản cho Android. Script cài chính thức
(`curl -LsSf https://astral.sh/uv/install.sh | sh`) tải binary biên dịch cho
**glibc** (`uv-aarch64-unknown-linux-gnu`), còn Android/Termux dùng **bionic**,
nên tải xong là chết (`exec format error`, `libc.so.6: not found`...). Trên PyPI
cũng không có wheel `android` nào cho `uv`.

Termux có gói `uv` riêng, build native từ source:

```bash
pkg install uv        # bản 0.13.8, chạy được trên bionic
```

Nếu lỗi của anh đến từ script `curl | sh` thì `pkg install uv` là cách thay thế
trực tiếp — vẫn là uv, chỉ khác nguồn cài.

## Nhưng thay `uv` thôi chưa đủ

Kể cả có `uv` chạy được, `uv sync` vẫn fail vì các gói của dự án chỉ có wheel
cho glibc:

| Gói | Vì sao chết trên Android |
| --- | --- |
| `markitdown` → `magika` → `onnxruntime` | PyPI không có wheel Android cho `onnxruntime` (Termux có gói riêng `python-onnxruntime`) |
| `fastapi` → `pydantic` → `pydantic-core` | Chỉ có wheel manylinux/macOS/Windows, không có Android |
| `uvicorn[standard]` → `uvloop`, `httptools`, `watchfiles` | Cùng lý do |
| `uv_build` (build backend cũ) | Không có wheel Android → không `pip install .` được |

`pip` trên Termux cũng tải đúng mấy wheel manylinux đó rồi lỗi lúc import, nên
đổi uv → pip không cứu được. Vì máy đã root, cách chắc ăn là chạy trong một
bản Linux **glibc** (Ubuntu/Debian) bằng `proot-distro`: uv, pip, wheel đều
chạy y như trên VPS.

Ghi chú: `pyproject.toml` đã đổi build backend từ `uv_build` sang `hatchling`
(thuần Python), nên `pip install -e .` không còn phụ thuộc uv nữa.

## Cách 1 — proot-distro + uv (khuyên dùng)

```bash
pkg install proot-distro
proot-distro install ubuntu          # Ubuntu 24.04, có Python 3.12 sẵn
proot-distro login ubuntu --shared-home
```

`--shared-home` mount thư mục home của Termux vào `/root` trong Ubuntu, để code
nằm sẵn ở đó. Trong shell Ubuntu:

```bash
apt update && apt install -y python3 python3-venv curl

cd ~/markitdown.kesbie.com
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
export UV_LINK_MODE=copy             # proot không thích hardlink

./run.sh serve --host 0.0.0.0 --no-open
```

Mở `http://<ip-máy-android>:8765` từ máy khác trong LAN.

### Không muốn dùng uv thì dùng pip

Trong Ubuntu, pip cài được đủ wheel (glibc):

```bash
cd ~/markitdown.kesbie.com
python3 -m venv .venv
.venv/bin/pip install -e .
./run.sh serve --host 0.0.0.0 --no-open   # run.sh tự thấy .venv
```

### Chạy nền / tự khởi động

Cài **Termux:Boot**, rồi tạo script (đường dẫn `/root/...` là home Termux vì
đã dùng `--shared-home`):

```bash
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/md2x.sh <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
proot-distro login ubuntu --shared-home -d -- /bin/bash -c '
  export PATH="$HOME/.local/bin:$PATH"
  export UV_LINK_MODE=copy
  exec /root/markitdown.kesbie.com/run.sh serve --host 0.0.0.0 --no-open \
       >> /root/md2x.log 2>&1
'
EOF
chmod +x ~/.termux/boot/md2x.sh
```

`--detach` bỏ stdout/stderr, nên phải tự redirect vào `/root/md2x.log` như trên.
Xem log: `tail -f ~/md2x.log` (file nằm trong home Termux).

## Cách 2 — Termux native, không qua proot (không khuyên)

Chỉ dùng khi không muốn cài thêm distro. `pkg install uv` chạy được, nhưng
`uv sync` vẫn chết ở các wheel glibc nêu trên. Muốn đi tiếp phải:

- `pkg install python python-pip python-numpy python-pandas python-lxml python-pillow python-onnxruntime python-cryptography`
- tạo venv với `--system-site-packages` để pip thấy các gói native Termux
  thay vì tải wheel manylinux;
- **build `pydantic-core` từ source** (Rust) — phần khó nhất: Termux có
  `rust`, `clang`, `maturin`, nhưng `maturin` trên PyPI là binary glibc, pip
  build-isolation sẽ không chạy được, phải tự build tay.

Trên thực tế bước cuối hay hỏng và tốn hàng chục phút trên điện thoại. Nếu
thật sự cần chạy native, hướng gọn hơn là bỏ FastAPI/pydantic, thay bằng
**Starlette thuần Python** (chỉ cần `starlette` + `uvicorn` + `python-multipart`
+ markitdown với `python-onnxruntime` của Termux). Khi đó không còn gì phải
biên dịch. Cần thì mở issue/nhắn để làm phần đó.

## Lưu ý khi chạy trên điện thoại

- **Không có xác thực** — chỉ mở `--host 0.0.0.0` khi thật sự cần LAN.
- RAM/CPU yếu hơn VPS: đặt `MD2X_MAX_FILE_MB=25` hoặc `50`, ví dụ
  `MD2X_MAX_FILE_MB=25 ./run.sh serve --host 0.0.0.0`.
- Convert chạy trong bộ nhớ; file PDF scan vẫn ra rỗng (pdfminer không OCR).
- `termux-wake-lock` để Android không ngủ giết tiến trình.
- proot chậm hơn chạy native (ptrace từng syscall), nhưng ổn định và đủ dùng
  cho việc convert lẻ tẻ. Muốn nhanh hơn và đã có root, có thể chroot thẳng
  vào rootfs của proot-distro (bỏ lớp proot), đổi lại phải tự mount
  `/dev`, `/proc`, `/sys` và home Termux).
