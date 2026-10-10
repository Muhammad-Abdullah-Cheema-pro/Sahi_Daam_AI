# Human voice recordings (optional)

Place one audio file per case id from `tests/voice_cases.csv`:

- Path pattern: `tests/voice_audio/<id>.<ext>` (e.g. `3.wav`, `4.mp3`)
- Record the **exact** spoken phrase below (Roman Urdu, Urdu script, or English as listed).

| id | phrase |
| ---: | --- |
| 1 | 40 maund tamatar hain Okara mein, broker 2800 de raha hai |
| 2 | mere paas 50 maund gandum hai Multan mein, rate 3800 rupay maund |
| 3 | ڈھائی سو من پیاز ہے سرگودھا میں، آڑھتی 1800 روپے من مانگ رہا ہے |
| 4 | I have 100 maunds of potatoes in Lahore, buyer offers 2500 rupees per maund |
| 5 | do hazar kilo tamatar Faisalabad mein hain 90 rupay kilo |
| 6 | chalees maund aloo Sahiwal mein hain |
| 7 | 30 maund pyaz Gujranwala, rate 1900 |
| 8 | mere paas 60 maund gandum hai Rawalpindi mein 3700 ka rate mil raha hai |
| 9 | ۴۰ من ٹماٹر اوکاڑہ میں ہیں ۲۸۰۰ روپے |
| 10 | pachas maund tamatar Kasur mein, 2600 rupay man |
| 11 | Pattoki mein 35 maund aloo hain, broker 2000 maang raha hai |
| 12 | 20 maund onion Multan, price 2100 |
| 13 | derh sau maund gandum Faisalabad 3900 rupay |
| 14 | ایک سو بیس من آلو لاہور میں |
| 15 | I have 75 maunds of wheat in Bahawalpur and the offer is Rs 3600 |
| 16 | tamatar 25 maund Sargodha mein 85 rupay kilo |
| 17 | 80 maund gandum Sialkot |
| 18 | dhai sau maund pyaz Okara 1750 rupay maund |
| 19 | 4000 kg aloo Multan 55 rupay per kg |
| 20 | mere paas 90 maund tamatar hain Jhang mein, rate 2400 hai |

Supported formats: WAV or MP3 (see `voice_engine.validate_audio`).
