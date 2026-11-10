# Xuất bản GEC Specifications v0.3 lên GitHub

Mục tiêu: tạo repository **private** `mepwegroup-code/GEC-SPEC` và push đầy đủ source code, không ghi đè repo website `mepwegroup-code/GEC`.

## Thực hiện trên Windows 10/11

1. Cài [Git](https://git-scm.com/download/win) và [GitHub CLI](https://cli.github.com/) (nếu chưa có).
2. Mở PowerShell/CMD, chạy `gh auth login`; đăng nhập GitHub với tài khoản `mepwegroup-code`.
3. Giải nén ZIP, mở thư mục `gec-specifications`, nhấp đúp `publish_to_github.bat` (hoặc chạy `powershell -File publish_to_github.ps1`).
4. Script xác nhận source, tạo Git commit, tạo repository private nếu chưa tồn tại, tự push nhánh `main` và mở trang repo.
5. Xem `Actions` trên GitHub để kiểm tra CI. Để deploy Vercel: New Project → Import Git Repository `GEC-SPEC` → Root Directory `frontend`; thiết lập biến môi trường theo README. Backend FastAPI cần deploy riêng.

**An toàn:** Script từ chối tài khoản khác, remote khác hoặc thay thế lịch sử Git (không force push). File `.env` thực, dữ liệu khách hàng và `node_modules` nằm trong `.gitignore`. Nếu repo đã tồn tại có lịch sử khác, lệnh push thất bại an toàn; cần kiểm tra thủ công.

## Lưu ý

Các bài kiểm thử trước đó **chưa** xác nhận production build Next.js hoặc đăng nhập Supabase thực tế. Không triển khai cho toàn công ty trước khi có kết quả CI xanh và kiểm tra staging với storage và backend thật.
