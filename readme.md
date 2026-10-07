# Telegram Otomatik Oylama

- Her gün her gün oy vermekten sıkılmadın mı?
- Yada oy vermeyi unuttuğun ve kalacağını bildiğin yemek için sana saat 2 de gel dediler.
- Bütün bunlardan sıkıldıysan tam sana göre bir uygulama yazdım.
- Telegram API'ı ile senin yerine oy kullanan bu küçük program sayesinde aç kalmaya son.

## Kurulum

```bash
    python -m venv .env
    source .env/bin/activate
    python -m pip install -r requirements.txt
```

## Kullanım

1. "example_config.yaml" dosyasının adını "config.yaml" olarak farklı kaydet.
2. "<https://my.telegram.org/>" adresinden giriş yap.
3. API development tools menüsünden "App api_id:" ve "App api_hash:" kısmındaki bilgileri "config.yml" içinde "accounts" altında uygun şekilde gir. Kullanmadığın "session" alanlarını silmeyi unutma.
4. Birden fazla  "accounts" ekleyerek farklı hesapları yönetebilirsin.
5. "rules" altından farklı oylamalar ekleyebilirsin.
6. İstersen “# , "Servis kullanacağım"” satırının yorumunu kaldırarak iki seçeneği de seçilebilir hale getirebilirsin. Yada yeni seçenekler girebilirsin.
7. "default_fallback: true" yaparsan seçeneklerin eşleşmemesi durumunda indeks olarak hangi seçeneklerini işaretleyeceğini girebilirsin.
8. Son olarak "target_channel" ayarının doğru olduğuna emin ol. Yanlış oylar kullanmak istemezsin.
9. Kodu çalıştır.

    ```bash
    python main.py
    ```

10. İlk çalıştırmada telefon numaranı ve sonrasında Telegram uygulamasına gelen doğrulama kodunu isteyecektir.
11. Afiyet olsun!
