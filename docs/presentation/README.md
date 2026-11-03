# M1 kısa kullanım sunumu

[Sunumu indir](AI-Act-Copilot-M1.pptx). 12 slayt, düzenlenebilir metinler ve ayrıntılı konuşmacı notları. Ekran örnekleri aynı araçları kullanan teknik belge alanından alınmıştır.

Langfuse kullanım adımları anlatılır. Bu ortamda anahtar bulunmadığı için canlı Langfuse ekranı veya doğrulanmış bir canlı model sonucu iddiası yoktur.

## 1. AI Act Copilot

Kaynağı görün. Kullanım amacını anlatın.
İncelemeyi birlikte geliştirin.

<details><summary>Sunucu notları</summary>

M1 kullanım rehberi. İç ekip ve ürün tanıtımı. Hukuki uygunluk belgesi üretmez.

</details>

## 2. Sistem ne yapıyor?

Bir kullanım senaryosu için ilgili resmi metinleri bulur.
Hangi kaynakları seçtiğini gösterir.
İnsan geri bildirimiyle tekrar kullanılabilir testler oluşturur.

<details><summary>Sunucu notları</summary>

Tam resmi kaynak paketi, yerel arama, isteğe bağlı Python incelemesi. Kaynak kapsamı kalite garantisi değildir.

</details>

## 3. Basit kullanım akışı

1  Kaynağı seçin
2  Kullanım amacını ve koşulları yazın
3  Bulunan metinleri inceleyin
4  Eksikleri işaretleyip test olarak kaydedin

<details><summary>Sunucu notları</summary>

Source explorer, Retrieval studio, Evaluation cases. Kod incelemesi isteğe bağlıdır. Gemini seçiliyse ayrı açık veri aktarımı onayı gerekir.

</details>

## 4. Kaynak ekranı

Source explorer

Resmi metinde arama yapın.
Paragrafı ve resmi bağlantısını açın.
Eksik kalmasını istemediğiniz kaynağı ekleyin.

<details><summary>Sunucu notları</summary>

Tüm kaynaklar sürüm ve özet değerleriyle sabittir. Koşullu uygulama tarihleri kesin sınıflandırma olarak gösterilmez. Hedef pasaj seçimi paragraf düzeyinde etiketlemeyi destekler.

</details>

## 5. Arama ve inceleme ekranı

Retrieval studio

Sistem ne yapıyor, kim kullanıyor?
Bulunan metinleri ve seçim adımlarını görün.
İsterseniz Python kodunu ayrıca inceletin.

<details><summary>Sunucu notları</summary>

Yerel FTS/BM25 ve CPU FastEmbed araması, Qdrant Local, RRF birleştirme, yeniden sıralama ve bağlantılı pasaj genişletme. Amaç/faktör çıkarımı ve kaynaklı inceleme iki sınırlı model geçişidir. Detaylar bölümünde gerçek amaç, niyetler, adaylar ve modele gönderilen pasajlar görünür.

</details>

## 6. Test ve geri bildirim ekranı

Evaluation cases

Gerekli, ilgili veya ilgisiz kaynakları işaretleyin.
Gerekçeyi yazın, taslağı kaydedin.
Onaylayın ve testi yeniden çalıştırın.

<details><summary>Sunucu notları</summary>

Onay yeni ve değiştirilemez bir revizyon oluşturur. Önceki taslak korunur. JSON dışa aktarma Git incelemesi içindir. Aynı bağlamdaki çelişen onaylı etiketler reddedilir. Tek vaka veya tüm geliştirme seti çalıştırılabilir. Recall@5/10, Precision, MRR, nDCG ve eksikler raporlanır.

</details>

## 7. Karşılaştırma ekranı

Compare runs

İki denemeyi yan yana açın.
Kullanım koşulları ve seçilen kaynaklar nasıl değişmiş?
Eklenen ve çıkan kaynakları görün.

<details><summary>Sunucu notları</summary>

Bağlamın kimliği ve RAG sürümü her koşuda saklanır. Bağlam değişince eski sonuç ve etiketler temizlenir. Aynı kaynak farklı kullanımda farklı değerlendirme gerektirebilir.

</details>

## 8. Kaynak ve arama sürümleri

RAG versions

Hangi metin ve arama ayarı bu sonucu üretti?
Yeni sürümü ayrı hazırlayın ve seçin.
Gerekirse önceki sürüme dönün.

<details><summary>Sunucu notları</summary>

Neden: resmi metin, paragraf ayrımı, gömme modeli veya arama mantığı değişebilir. Her yapı içerik adresli manifest ve doğrulanan kaynak/vektör dosyaları içerir. Uygulama sürümü, kaynak sürümü, arama sürümü ve test revizyonu ayrıdır. Yerel etkinleştirme nihai kalite onayı değildir.

</details>

## 9. Langfuse ile incelemeyi izleme

Bir inceleme ne kadar sürdü? Nerede hata oldu?

Kod toplama, amaç çıkarma, arama, inceleme ve doğrulama.
Gerçekte mevcutsa kullanım miktarı.
İnceleme ekranından ilgili kayda bağlantı.

<details><summary>Sunucu notları</summary>

Kullanım: özel .env içinde LANGFUSE_ENABLED=true, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY ve LANGFUSE_PROJECT_ID ayarlayın. API’ı yeniden başlatın. İzinli bir inceleme çalıştırın, sonuçtaki Open metadata-only Langfuse trace bağlantısını açın. Langfuse EU sabit adreslidir. Ham kod, istem, yanıt ve anahtar aktarılmaz. Erişilemezse incelemeyi bozmaz. Bu ortamda anahtar bulunmadığından canlı Langfuse kaydı doğrulanmamıştır. Slayt canlı ekran görüntüsü iddiası taşımaz.

</details>

## 10. Langfuse kullanım adımları

1  Özel .env dosyasında bağlantıyı açın
2  İzinli bir kod incelemesi çalıştırın
3  Sonuçtaki Langfuse bağlantısını açın
4  Süreyi, adımları ve hatayı kontrol edin

<details><summary>Sunucu notları</summary>

360 resmi kaynak, 119 madde, 14 ek, 180 ilk düzenleme ve 47 değişiklik gerekçesi. SQLite yerel saklama, PostgreSQL eşlik testleri. Docker Compose gerçek kurulum/restart ve paketleme CI’da doğrulandı. Güncelleme kontrolü resmi metadata okur; staging son iyi sürümü değiştirmez. Yeni hukuk sürümü için kaynak politikası/parser incelemesi gerekir.

</details>

## 11. Platform nasıl genişler?

Yeni belge alanı aynı ekranları kullanabilir.
Model değişirken inceleme akışı korunur.
Daha büyük kurulumda saklama katmanı değişebilir.

<details><summary>Sunucu notları</summary>

İkinci teknik belge alanı aynı API, etiketleme ve değerlendirme yolunu kullanır. Python modülleri: kaynak, sözleşme, saklama, gömme, arama, inceleme ve değerlendirme. React + Vite inceleme arayüzüdür. Gemini ve Ollama ayrı sağlayıcılardır, otomatik geçiş yoktur. DATABASE_URL seçimi veri taşımaz. Qdrant Local tek süreç sahibidir. Çok kullanıcılı ürün ve bulut dağıtımı sonraki aşamadır.

</details>

## 12. İlk deneme ve kalan kabul

Kurulum: docker compose up --build
Tarayıcı: 127.0.0.1:8000
Önce kaynak ve arama ekranlarını deneyin.

Canlı model doğrulaması ve uzman test onayı açık.

<details><summary>Sunucu notları</summary>

İlk kurulum yerel gömme modelini indirir. Arama için Gemini anahtarı gerekmez. Gemini isteğe bağlıdır ve kaynak aktarımı onayı ister. 54 yasal senaryo model taslağıdır; uzman gold değildir. 50+ uzman onaylı vaka, ayrı holdout ve kritik set nihai M1 kabul koşuludur. Teknik hazır olma tam yasal kalite kabulü değildir. README ve docs/M1-STATUS.md güncel sınırları kaydeder.

</details>
