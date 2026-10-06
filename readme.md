# Telegram Otomatik Oylama

- Her gün her gün oy vermekten sıkılmadın mı?
- Yada oy vermeyi unuttuğun için atılacağını bildiğin yemek için sana saat 2 de gel dediler.
- Bütün bunlardan sıkıldıysan tam sana göre bir uygulama yazdım.
- Telegram API'ı ile senin yerine oy kullanan bu küçük program sayesinde aç kalmaya son.

## Kurulum

```bash
    python -m venv .env
    source .env/bin/activate
    python -m pip install -r requirements.txt
```

## Kullanım

1. "<https://my.telegram.org/>" adresinden giriş yap.
2. API development tools menüsünden "App api_id:" ve "App api_hash:" kısmındaki bilgileri kodun içinde "ACCOUNTS_CONFIG" altında uygun şekilde gir.
3. Kodu çalıştır.

    ```bash
    python main.py
    ```

4. İstersen “# , "Servis kullanacağım"” satırının yorumunu kaldırarak iki seçeneği de seçilebilir hale getirebilirsin.
5. Birden fazla  "ACCOUNTS_CONFIG" ile farklı hesaplar ve "POLL_RULES" ile farklı oylamalar ekleyebilirsin.
6. İlk çalıştırmada telefon numarası ve sonrasında doğrulama kodu isteyecektir.
