# Deploy md2x

md2x là app ASGI bình thường, nghe ở `127.0.0.1:8765`. Nginx đứng trước làm
TLS, giới hạn upload và (tuỳ chọn) đặt mật khẩu.

```
Internet → nginx :443 → md2x :8765
```

## Cách 1 — systemd (gọn nhất cho VPS)

```bash
# 1. Tạo user và đưa code lên
sudo useradd -r -s /usr/sbin/nologin -d /opt/md2x md2x
sudo rsync -a --exclude .venv --exclude .uvcache ./ /opt/md2x/
sudo chown -R md2x:md2x /opt/md2x

# 2. Cài uv (nếu chưa có) và phụ thuộc
curl -LsSf https://astral.sh/uv/install.sh | sudo sh
sudo -u md2x bash -c 'cd /opt/md2x && UV_CACHE_DIR=/opt/md2x/.uvcache uv sync --no-dev'

# 3. Chạy nền
sudo cp deploy/systemd/md2x.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now md2x
curl localhost:8765/healthz        # {"status":"ok"}

# 4. Nginx
sudo cp deploy/nginx/md2x.conf /etc/nginx/sites-available/md2x.conf
sudo sed -i 's/md2x.example.com/domain-that-cua-anh.com/g' /etc/nginx/sites-available/md2x.conf
sudo ln -s /etc/nginx/sites-available/md2x.conf /etc/nginx/sites-enabled/
sudo certbot --nginx -d domain-that-cua-anh.com
sudo nginx -t && sudo systemctl reload nginx
```

Kiểm tra `which uv` rồi sửa `ExecStart` trong
[md2x.service](<systemd/md2x.service>) cho khớp đường dẫn thật.

## Cách 2 — Docker

```bash
docker compose up -d --build
curl localhost:8765/healthz
```

Rồi vẫn dùng [md2x.conf](<nginx/md2x.conf>) ở nginx trên host như bước 4 ở trên.

## Chọn file nginx nào

| File | Dùng khi |
| --- | --- |
| [md2x.conf](<nginx/md2x.conf>) | Domain riêng, có HTTPS — trường hợp thường gặp |
| [md2x-basicauth.conf](<nginx/md2x-basicauth.conf>) | Muốn đặt mật khẩu + chặn spam (md2x không có sẵn xác thực) |
| [md2x-subpath.conf](<nginx/md2x-subpath.conf>) | Gắn vào site sẵn có dưới dạng `/md2x/` |

## Hai con số phải khớp nhau

Nếu lệch, nginx chặn trước và trình duyệt nhận lỗi 413:

| Chỗ | Giá trị |
| --- | --- |
| nginx | `client_max_body_size 200m;` |
| app | `MD2X_MAX_FILE_MB=200` |

Muốn cho phép file 500MB thì sửa **cả hai** rồi `systemctl reload nginx` và
`systemctl restart md2x`.

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `MD2X_MAX_FILE_MB` | `200` | Dung lượng tối đa mỗi file |
| `MD2X_MAX_FILES` | `50` | Số mục tối đa mỗi lần convert |

Giá trị sai hoặc ≤ 0 sẽ tự rơi về mặc định.

## Lưu ý vận hành

- **Không có xác thực sẵn.** Mở ra Internet thì nên dùng bản basicauth, hoặc
  chặn theo IP, hoặc để sau VPN.
- **Tốn CPU và RAM theo kích thước file** — convert chạy trong bộ nhớ. VPS 1GB
  nên hạ `MD2X_MAX_FILE_MB` xuống còn 25–50.
- **Timeout để 600s** vì PDF lớn và transcript YouTube có thể chạy lâu.
- **Không ghi file ra đĩa**, nên không cần volume và không phải dọn rác.
- Xem log: `journalctl -u md2x -f` hoặc `docker compose logs -f`.

## Sự cố thường gặp

| Triệu chứng | Nguyên nhân |
| --- | --- |
| 413 Request Entity Too Large | `client_max_body_size` nhỏ hơn file |
| 504 Gateway Time-out | File lớn, tăng `proxy_read_timeout` |
| 502 Bad Gateway | md2x chưa chạy — `systemctl status md2x` |
| Trang hiện nhưng nút Convert báo lỗi | Sai subpath; nhớ có dấu `/` cuối và cả hai block `location` |
| `unknown directive "http2"` | nginx < 1.25.1 — xem ghi chú trong file conf |
