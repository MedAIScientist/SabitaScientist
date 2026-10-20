# Klinik Kohort Analiz Modülü — Yol Haritası

Kaynak proje: [KarimELMERNISSI/Cohort-Studio](https://github.com/KarimELMERNISSI/Cohort-Studio) (Apache-2.0, v2.4.1)

Hedef: IRB onaylı bir veri setinden başlayıp, makalede savunulabilir bir
**analiz popülasyonu + participant flow + istatistiksel sonuç + kanıt dosyası**
üreten; her sayının hangi veri sürümünde, hangi popülasyonda, hangi N ile
hesaplandığını söyleyen bir modül. Sonuçlar mevcut `experiment_metrics` →
`verify_numbers` zincirine bağlanır, böylece AI taslağına giren sayı
doğrulanabilir olur.

Durum anahtarı: ✅ tamam · 🔴 bloklayıcı · 🟡 önemli · 🟢 sonra

---

## Uygulama durumu

Faz 1–7 ve güç analizi **uygulandı**. Yalnızca SMR bilinçli olarak açık (gerekçe: sapma 7).

| Faz | Durum | Nerede |
|---|---|---|
| 1 — Veri kaydı, popülasyon, participant flow | ✅ | `gazzali/cohort/{ingest,store,engine}.py`, `crud/cohort.py`, `api/routes/cohort_analysis.py` |
| 2 — Kalite skorkartı + hash-zincirli iz + replay | ✅ | `gazzali/cohort/{quality,transform}.py`, `crud.cohort.verify_chain`, `POST …/replay` |
| 3 — Tanımlayıcı / Tablo 1 / grup karşılaştırma | ✅ | `gazzali/cohort/analyses.py` (`descriptive`, `table1`, `compare`) |
| 4 — Provenans, bayat işareti, metrik köprüsü | ✅ | `crud.cohort.analysis_is_stale`, `POST …/publish`, `verify_numbers._LIVE_COHORT_METRIC` |
| 5 — Sağkalım / tanısal doğruluk / epi oranları | ✅ | `analyses.py`: `survival`, `cox`, `logistic`, `diagnostic`, `ratio_2x2`, `mantel_haenszel`, `agreement` |
| 5b — Güç / tespit edilebilir fark | ✅ | `analyses.py`: `power` — MDE + seçilen fark için güç + planlama için gerekli n |
| 5c — `smr` | ⬜ | ertelendi: popülasyona bağlı değil, dış referans hızı gerektiriyor (gerekçe: sapma 7) |
| 6 — MCAR + MI + Rubin | ✅ | `analyses.py`: `mcar`, `multiple_imputation` (target `compare`/`logistic`/`cox`) |
| 6b — R paritesi | ✅ | `tests/pm/test_cohort_mi_parity.py` + `tests/pm/fixtures/mi/` — R `mice` 3.19 / `mitml` 0.4.5 |
| 7 — Study dossier | ✅ | `gazzali/cohort/dossier.py` (python-docx) + `GET …/dossier` + Report sekmesi |

Arayüz: `/projects/:id/cohort` (`CohortPage.tsx`) — sekmeler: Data · Population · Analysis · Quality · Provenance · Report.

Testler: `tests/pm/test_cohort_engine.py` (81), `tests/pm/test_cohort_api.py` (53), `tests/pm/test_cohort_dossier.py` (18), `tests/pm/test_cohort_mi_parity.py` (10, R paritesi) — 162 test.

**Plandan bilinçli sapmalar:**

1. **Ayrı `gazzali-analysis` worker'ı yok.** İstatistik, FastAPI'nin thread havuzunda
   koşuyor (`def` handler) ve importer 500k satır tavanı koyuyor. `gazzali/cohort`
   hiçbir yerde SQLite veya FastAPI import etmiyor, yani worker'a taşınmak kod
   değişikliği değil dağıtım değişikliği. 100k satır kararınız için bu yeterli.
2. **Sürüm dosyaları Garage'ta değil, yerel diskte.** `GAZZALI_COHORT_DIR`
   (varsayılan `<workspace>/cohort`, prod'da `/data/workspaces/cohort` — kalıcı
   volume). Analiz dosyası her istekte okunuyor; S3 gidiş-dönüşü burada maliyet,
   fayda değil.
3. **İz adımları:** `import`, `derive`, `filter`, `population`. `impute`/`clip`/
   `convert`/`merge` şemada var ama yazan bir yol yok — faz 6'ya kadar gerekmiyor.
4. **Kalite skorkartı** IQR + z-skoru kullanıyor; Isolation Forest/LOF/DBSCAN yok
   (sklearn eklenmedi). Klinik kurallar çalışıyor (config'teki `bounds`/`expression`).
5. **`governed` kapısı yazıldı ama varsayılan değil.** Kararınız gereği ilk aşama
   yalnızca public/synthetic; kapı (`dataset` onayı + grant + süresi geçmemiş IRB)
   hazır ve test edilmiş durumda, `data_origin='governed'` seçilince devreye giriyor.
6. **Sağkalımda PH testi ve konkordans `lifelines` ister.** Kurulu değilse sonuç
   tablosu bunu açıkça yazıyor ("... need the optional 'survival' extra"), sessizce
   atlamıyor. `lifelines` eklendiği gün ikisi de kendiliğinden görünür.
7. **Güç analizi yapıldı, SMR yapılmadı.** Güç hesabını önce "planlama işi, hibe
   modülüne ait" diye ertelemiştim; bu yanlıştı. Bir *hassasiyet* ifadesi
   ("bu kohort 5.4 puanlık farkı yakalayabilirdi") tam olarak popülasyona bağlıdır ve
   makalenin limitasyon paragrafının istediği cümledir. `power` bunu veriyor.
   SMR ise gerçekten dışarıda: `observed / expected` oranı, kohortta olmayan bir
   referans hızı gerektiriyor, yani popülasyona bağlı bir analiz değil.
   **Post-hoc power tuzağı bilinçle ele alındı:** örneklemde görülen farkı isimlendirmek
   güç hesabını p-değerinin tekrarı yapar; `power` bunu tespit edip tabloda uyarıyor
   (%1 toleransla) ve kendi MDE'si için gereken n'nin gözlenen n'ye eşit çıkması
   testle kilitlendi.
8. **Her metot `publish` edilebilir sayı üretiyor** (`HR`, `p`, `AUC`, `OR`, `kappa`
   …). Yani sağkalım, lojistik, tanısal, 2x2, MH ve uyum sonuçları da
   `experiment_metrics`'e yazılıp `verify_numbers` tarafından görülebiliyor; bunun
   testi `test_a_survival_value_can_be_published_like_any_other`.
9. **MI bir *analiz*, bir veri sürümü değil.** Imputation `cohort_versions`'a yeni bir
   tablo yazmıyor: m imputed veri kümesi bir hesaplamanın ara ürünü, kayıt değil.
   Provenans `cohort_analyses.params_json` içinde (m, maxit, seed, model kolonları),
   populasyon parmak izine bağlı. Tek imputasyonla "doldurulmuş" bir tablo
   üretilmiyor — bu modül tek imputasyonu çıkarım için hiç sunmuyor.
10. **Pooled çıktı complete-case ile yan yana.** Ayrı satırlar değil, ayrı *kolonlar*:
   asıl bilgi ikisinin farkında. Başarısız/ayrışmış bir pooling sessizce geçmiyor —
   R-hat > 1.05 ise not düşülüyor, hedef tek bir tahmin değilse (3 gruplu ANOVA)
   net bir hatayla reddediliyor.
11. **Dossier bir `.docx`, HTML→`.doc` değil.** `python-docx` eklendi: gerçek başlıklar
   ve tablolar, Word'ün "bu dosyayı açamıyorum" uyarısı olmadan. Participant flow bir
   **tablo** olarak basılıyor (adım, n, elenenler, gerekçe) — matplotlib ile çizilmiş bir
   figür değil. Bu bilinçli: tablo, figürün iddia ettiği her sayıyı zaten taşıyor ve yeni
   bir ağır bağımlılık gerektirmiyor. Figür istenirse sonraki artırım.
12. **Dossier varsayılan olarak yalnızca güncel sonuçları alır.** Superseded popülasyondaki
   bir sonuç, ancak adıyla istenirse girer — o zaman belgede **"Stale result"** olarak
   işaretlenir ve "güncel olarak raporlanmamalıdır" cümlesiyle birlikte. Adıyla istenen
   sonuç, tablonun *tüm* popülasyonlarında aranır (ilk sürümde yalnız aktif popülasyona
   bakıyordu ve 404 veriyordu; test bunu yakaladı).
13. **Belgenin ilk paragrafı bir uyarıdır.** "Bu bir uyumluluk sertifikası değildir ve
   elektronik imzalı bir kayıt değildir; STROBE/CONSORT/PRISMA uyumunu belgelemez."
   Metnin hiçbir yeri bunun aksini ima etmiyor; test bunu kilitliyor.
11. **Upstream'de bir hata bulundu ve düzeltildi.** `biostats/mi/analyze.py:67`
   upstream'de Python 2 sözdizimi (`except TypeError, ValueError:`) içeriyor; bu,
   `biostats.mi` paketini o revizyonda import edilemez yapıyor. Düzeltme
   `vendor/NOTICE`'ta kayıtlı, upstream'e bildirilmeli.

---

## 0. Yönetici özeti

Cohort-Studio bir **klinik kohort analiz tezgâhı**: Streamlit + DuckDB + Parquet,
yerel-öncelikli, tek kullanıcı odaklı. Gazzali ise bir **araştırma yönetimi
platformu**: IRB, veri seti onayı, hibeler, yayın hattı, denetim izi var; ama
istatistik motoru **hiç yok** (`scipy`/`pandas`/`numpy`/`statsmodels` importu
sıfır, doğrulandı).

Üç cümlelik yargı:

1. **Kopyalanacak en değerli şey istatistik kodu değil, "kanıt disiplini"**:
   ilan edilmiş analiz popülasyonu, STROBE participant flow, hash-zincirli
   veri soy kütüğü, "bu sonuç bayat" işareti ve Word kanıt dosyası.
2. **İstatistik çekirdeğini yeniden yazmak en pahalı ve en riskli yol.**
   Cohort-Studio'nun `core/` ve `biostats/` paketleri arayüzden bağımsız
   (`tests/test_layering.py` bunu zorluyor), sadece numpy/pandas/scipy/
   statsmodels'e bağlı. Apache-2.0 bunu vendor'lamaya izin verir; Rubin
   kuralları ve Hedges' g güven aralığı gibi doğru yapılması zor parçalar
   hazır gelir.
3. **Streamlit/DuckDB/Parquet depolama modelini kopyalamayın.** Gazzali'de
   zaten SQLite + Garage S3 + lab/proje RBAC var. Ağır istatistiği API
   sürecinde değil, ayrı bir **analysis worker**'da çalıştırın — tıpkı
   `researchclaw` servisi gibi.

Efor: **~35–50 geliştirici-günü**, 7 fazda. Faz 1–2 (popülasyon + flow +
kalite) tek başına makale için en yüksek getiriyi verir ve **yeni bağımlılık
gerektirmez**.

---

## 1. Cohort-Studio'da ne var

| Alan | Ne yapıyor | Bizim için değeri |
|---|---|---|
| Analiz popülasyonu | Sidebar'dan tik atılan inklüzyon/eksklüzyon kriterleri; satır silmez, her sayfayı filtreler | ⭐⭐⭐⭐⭐ |
| Participant flow | STROBE madde 13 diyagramı, her kutu tıklanabilir, sayımların tutarlılığı test edilir | ⭐⭐⭐⭐⭐ |
| Hash-zincirli trace + verified replay | Her veri değişikliği bir adım; SHA-256 zinciri; replay aynı tabloyu üretiyor mu diye kontrol | ⭐⭐⭐⭐⭐ |
| Sonuç provenansı | Her sonuç "hangi veri + hangi popülasyon + N" der; eski veride hesaplanan sonuç "güncel" görünmez | ⭐⭐⭐⭐⭐ |
| Study dossier (.docx) | Provenans + flow + veri işleme + eksik veri + sonuçlar + kaynaklar | ⭐⭐⭐⭐ |
| Multiple imputation + Rubin | `mice` uyumlu zincirleme denklemler, R `mice` 3.19 / `mitml` 0.4.5 ile 1e-10 parite testi, MICE tanıları | ⭐⭐⭐⭐ (zor) |
| Kalite skorkartı | Tamlık, benzersizlik, tutarlılık, tekdüzelik, istatistiksel geçerlilik, klinik anomali kuralları | ⭐⭐⭐⭐ |
| Etki büyüklükleri + GA | Hedges' g (noncentral-t GA), rank-biserial r, η²/ω², Cramér's V; Holm/BH/Bonferroni | ⭐⭐⭐⭐ |
| Sağkalım / regresyon | KM + Greenwood, log-rank, Cox (Efron, Grambsch-Therneau), lojistik (DeLong AUC), Poisson | ⭐⭐⭐⭐ |
| Tanısal doğruluk / uyum | ROC, sens/spec/PPV/NPV, LR±, kappa, ICC, Bland-Altman | ⭐⭐⭐ |
| 2x2 epidemiyoloji | RR/OR/RD, Haldane-Anscombe, Mantel-Haenszel, SMR, Breslow-Day | ⭐⭐⭐ |
| Türetilmiş değişken editörü | Sandbox'lı ifade dili + önizleme + replay'de yeniden hesaplama | ⭐⭐⭐ |
| AI öneri motoru | Sütun adı/variable formülü önerir, **hiçbir şeyi otomatik uygulamaz** | ⭐⭐⭐ |
| 14 grafik + anlamlılık parantezleri | Plotly, SVG/HTML/CSV export | ⭐⭐ (bizde matplotlib hattı var) |
| Bilgi grafiği / variable map | Değişken ilişki ağı | ⭐ (copilot var) |
| IAM, workspace, yFiles | Kendi IAM'i, kullanıcı başına workspace, tescilli render | ❌ alınmaz |

---

## 2. Gazzali'de bugün nerede duruyoruz

| Yetenek | Gazzali bugün | Sonuç |
|---|---|---|
| IRB onayı | ✅ `irb_approvals` | Kohort modülü buna **bağlanmalı** — Cohort-Studio'da yok, bizim avantajımız |
| Veri seti yönetişimi | ✅ `datasets` (draft→pi_approved→approved→sealed), `dataset_irbs`, `dataset_grants` | Analizin ön koşulu burada hazır |
| De-identification | ✅ `deid_pipelines`, `deid_pipeline_runs` | Kohort verisi deid'den geçmiş olmalı |
| Denetim izi | ✅ `audit_log` (kim, ne, hangi IP) | **Veri soy kütüğü değil**: "sayı neyden hesaplandı" sorusunu yanıtlamıyor |
| Ölçülmüş sonuçlar | ✅ `experiment_metrics` (`source` kolonu var: csv/manual/ai_run) | Kohort sonuçları buraya **köprülenmeli** |
| Sayı doğrulama | ✅ `verify_numbers.py` — kayıtlı metrikle eşleşmeyen sayıyı `[UNVERIFIED]` işaretler | Kohort sonuçları buraya akarsa değer katar |
| Makale hattı | ✅ drafting, `paper_claim_map`, `paper_integrity_runs` | Dossier ve flow doğrudan buraya girer |
| Hesaplama altyapısı | ✅ `compute/` (Local/SLURM/SSH), `sandboxes`, `researchclaw` worker | Analiz burada koşmalı |
| **İstatistik motoru** | ❌ yok (scipy/pandas/numpy/statsmodels importu sıfır) | Ana boşluk |
| **Analiz popülasyonu / flow** | ❌ yok (`cohort.py` akademik öğrenci kohortu, ilgisiz) | Ana boşluk |
| **Provenans / replay** | ❌ yok | Ana boşluk |
| Word çıktı | 🟡 HTML→`.doc` var (`progress_report.py`), gerçek `.docx` yok | Dossier için yeterli başlangıç |

---

## 3. Stratejik karar: vendor / yaz / alma

### ✅ Vendor — `core/` ve `biostats/`

`gazzali/cohort/vendor/` altına, `NOTICE` + kaynak atfıyla:

| Vendor'lanacak | Neden |
|---|---|
| `core/criteria.py`, `core/population.py` | Kriter aileleri, satır silmeyen filtreleme, popülasyon parmak izi |
| `core/attrition.py` | Participant flow modeli + `inconsistencies()` tutarlılık kontrolü |
| `core/fingerprint.py`, `core/lineage.py` | Hash zinciri ve satır-aralığı parmak izi |
| `core/expressions/safe_eval.py` | Beyaz listeli ifade sandbox'ı |
| `biostats/` (tümü) | Welch-first testler, etki büyüklükleri + GA, posthoc, çoklu test, MCAR, tanısal, uyum, sağkalım, regresyon, güç analizi, **`mi/` (Rubin havuzlama)** |
| `biostats/references.py` | Her testin kaynağı → metot paragrafı ve dossier kaynakçası |

**Almayın:** `core/workspace.py`, `core/session.py`, `core/state.py`,
`core/progress.py` (Streamlit'e özgü), `app_pages/`, `ui/`, `manage/iam/`,
`manage/rag*`, `graph/renderers/yfiles.py`.

**Lisans:** Apache-2.0 → ticari/akademik kullanım serbest, ama `NOTICE` ve
dosya başlıklarını korumak zorunlu. `biostats` içindeki yöntem atıfları
(Steiger 2004, Barnard-Rubin 1999, Little 1988, Sterne 2009 …) korunmalı:
bunlar hem lisans hem akademik dürüstlük gereği.

**Doğrulama:** vendor'lanan paketin testlerinden `test_lineage.py`,
`test_population.py`, `test_attrition.py`, `test_effect_sizes.py`,
`test_mi_pooling.py`, `test_mi_r_parity.py` + `tests/reference/fixtures/mi/`
birlikte taşınır. R parite fixture'ları olmadan MI'ya güvenmeyin.

### ✍️ Yeniden yaz — ürün katmanı

Popülasyon UI'ı, provenans kartları, FastAPI rotaları, React sayfaları,
dossier, `experiment_metrics` köprüsü, IRB/dataset/grant kapıları. Bunlar
Gazzali'ye özgü ve Cohort-Studio'da karşılığı yok.

### ❌ Alınmaz

Streamlit arayüzü · DuckDB+Parquet deposu · kullanıcı başına workspace ·
kendi IAM'i · yFiles · RAG/bilgi grafiği · 14'lük grafik galerisi ·
`CMP_*` konfigürasyon şeması.

---

## 4. Hedef mimari

```
React  /projects/:id/cohort          (CohortPage)
   │
FastAPI  api/routes/cohort.py        (mevcut supervision cohort'undan ayrı: /api/v1/cohort)
   │  popülasyon kriterleri, job kuyruğu, provenans
   ├──────────────► SQLite: cohort_tables / versions / populations / analyses
   │                        (trace: cohort_steps, hash-zincirli)
   └── HTTP ──────► gazzali-analysis worker (internal, CPU, egress yok)
                       gazzali/cohort/vendor/{core,biostats}
                       pandas + DuckDB → Parquet okur, sonucu döner
```

Worker ayrı bir compose servisi (`deploy/analysis/`), `researchclaw` ile aynı
desen: internal-only, CPU limitli, `ANALYSIS_WORKER_URL` + token ile erişilir.
Böylece ana API imajı ~300 MB büyümez, ağır hesap API sürecini kilitlemez.

**Veri nerede?** Sürüm dosyaları Garage S3'te (`cohort/versions/<id>.parquet`),
SQLite sadece üst veriyi tutar. Ham CSV/Excel yüklemesi mevcut `attachments`
hattından geçer.

---

## 5. Fazlar

### ✅ Faz 1 — Veri kaydı, popülasyon, participant flow

**Problem.** Bugün bir hocanın "bu makalede kaç hasta analiz edildi, kimler
dışlandı ve neden" sorusunun cevabı sistemde yok. Hakem ve dergi editörü
STROBE flow diyagramı istiyor.

**Yapılacak.**
- `POST /cohort/tables` + `POST /cohort/tables/{id}/versions` (CSV/XLSX/Parquet
  yükle → parse raporu → sürüm).
- `cohort_tables.dataset_id` verilmişse: `datasets.status IN ('approved','delivering','sealed')`
  **ve** projeye `dataset_grants` verilmiş **ve** IRB onaylı **ve** süresi
  geçmemiş olmalı. Değilse 403 — mevcut `research_runs` IRB kontrolüyle aynı desen.
- Kriter aileleri (`study config`): inklüzyon (`all`), anomali/aykırı değer
  (`any`), eşik (`at least k`). `core/population.evaluate_population` çağrılır.
- `GET /cohort/populations/{id}/flow` → `core/attrition.ParticipantFlow`
  (kaynak → okunan → elenen → popülasyon → analiz N).
- Frontend: `/projects/:id/cohort` + sekmeler: **Veri · Popülasyon · Kalite ·
  Analiz · İz · Rapor**.

**Dosyalar.** `db.py` (+5 tablo, migration), `models.py`, `api/schemas.py`,
`crud/cohort.py`, `api/routes/cohort.py`, `api/app.py`,
`frontend/src/pages/CohortPage.tsx`, `main.tsx`, `api.ts`,
`gazzali/cohort/{__init__,ingest,population,flow}.py`, `gazzali/cohort/vendor/`.

**Efor.** 5–7 gün. **Yeni bağımlılık:** pandas, pyarrow (worker içinde).

**Doğrula.** Tutorial kohortu (`assets/tutorial/tutorial_cohort.csv`) yüklenir;
flow sayımları `inconsistencies() == []` döner; popülasyondan bir kriter
kaldırılınca N artar ve flow yeniden hesaplanır. `tests/pm/test_cohort_api.py`.

---

### ✅ Faz 2 — Kalite skorkartı + hash-zincirli iz + replay

**Problem.** `audit_log` "kim ne yaptı"yı tutuyor, "sayı neyden çıktı"yı
tutmuyor. Veri bir kez düzenlendiğinde geri iz sürülemiyor.

**Yapılacak.**
- Veri kalitesi: tamlık, benzersizlik, tutarlılık (yanlış tipli sayı/tarih,
  boşluk, büyük/küçük harf), tekdüzelik + IQR/z-skor aykırı değer. Klinik
  anomali kuralları JSON'dan (sınır veya ifade). Skor, `dataset` onay kapısına
  gösterge olarak eklenir (onayı **engellemez**, bilgilendirir).
- `cohort_steps`: her yazma yolu tek bir fonksiyondan geçer
  (`gazzali/cohort/write_path.py`), adım `prev_hash → hash` ile zincirlenir.
- `GET /cohort/versions/{id}/replay?mode=fast|full` → adımlar yeniden koşar,
  her adımın parmak izi karşılaştırılır, uyuşmazlıklar listelenir.
- Trace raporu: HTML→`.doc` (mevcut `progress_report` desenini kullan).

**Efor.** 5–7 gün. **Bağımlılık:** yok (Faz 1'in worker'ı içinde).

**Doğrula.** Bir adımın parametresi elle bozulur → replay `tampered` döner;
replay sonrası tablo parmak izi orijinalle aynı. `test_cohort_trace.py`.

---

### ✅ Faz 3 — Tanımlayıcı istatistik, Tablo 1, grup karşılaştırma

**Problem.** Her klinik makalenin ilk tablosu "Table 1". Bugün elle Excel'de
yapılıyor, o yüzden N ve p-değeri metindekiyle tutmuyor.

**Yapılacak.**
- `POST /cohort/populations/{id}/analyses` · `method=table1`:
  nicel değişkenler (doluluk, çeyreklikler, normallik testi), nitel değişkenler
  (en sık değerler), grup kolonu verilirse Welch t / Mann-Whitney /
  Welch ANOVA / Kruskal-Wallis + **etki büyüklüğü ve GA** + Holm (varsayılan) /
  BH / Bonferroni.
- `method=compare`, `method=correlation`.
- Varsayım kontrolleri **tanı**dır, kapı değil — Cohort-Studio'nun kuralı
  aynen korunur ve sonuç kartında açıkça yazılır.
- Her tablo Excel/CSV indirilebilir; her hücre `cohort_analysis_values`'a yazılır.

**Efor.** 4–6 gün. **Bağımlılık:** scipy (+ vendor `biostats`).

**Doğrula.** R ile üretilmiş referans fixture'ları; `test_cohort_table1.py`.

---

### ✅ Faz 4 — Sonuç provenansı, bayat işareti, metrik köprüsü

**Problem.** Bu modülün varlık sebebi. Bir sonuç, hesaplandığı veri/popülasyon
değiştiğinde hâlâ "güncel" görünürse, modül fayda değil zarar verir.

**Yapılacak.**
- `cohort_analyses.population_fingerprint` ile popülasyonun güncel parmak izi
  karşılaştırılır; farklıysa `status='stale'`. UI'da "bu sonuç başka bir
  popülasyonda hesaplandı" uyarısı; varsayılan olarak gizlenir.
- Her sonuç kartı: yöntem + popülasyon adı + veri sürümü + N + hesaplama zamanı.
- `POST /cohort/analyses/{id}/publish` → seçilen sayılar (`HR`, `p`, `N` …)
  `experiment_metrics`'e yazılır, `source='cohort'`,
  `source_analysis_id` (yeni kolon) ile geri bağlanır.
- Böylece `verify_numbers.recorded_values()` bu sayıları görür: AI taslağındaki
  HR/p artık `[UNVERIFIED]` olmaz, çünkü gerçekten kayıtlı.

**Efor.** 3–4 gün. **Bağımlılık:** yok.

**Doğrula.** Kohort sonucu publish edilir → `draft-paper` çağrısında o sayı
doğrulanmış sayılır; popülasyon değişir → sonuç `stale`, publish edilmiş metrik
`verify_numbers`'da **uyarı** üretir (sessizce geçerli kalmasın).
`test_cohort_metrics_bridge.py`.

---

### ✅ Faz 5 — Sağkalım, tanısal doğruluk, epidemiyolojik oranlar

**Problem.** Kohort çalışmalarının asıl çıktısı HR/OR/AUC; bunlar olmadan modül
yarım.

**Yapılacak.**
- `method=km` (Greenwood GA, log-rank), `method=cox` (Efron ties, PH kontrolü),
  `method=logistic` (OR, DeLong AUC), `method=poisson` (person-time offset).
- `method=roc` (sens/spec/PPV/NPV/LR±/Youden), `method=agreement` (kappa, ICC,
  Bland-Altman), `method=ratio2x2` (RR/OR/RD + Haldane-Anscombe),
  `method=mantel_haenszel`, `method=smr`.
- `method=sample_size` (vendor `biostats/power.py`; toplam/grup-başı
  semantiği açıkça yazılı) — başvuru aşamasında güç hesabı; IRB/hibe formlarına
  gerekli N olarak akar.

**Efor.** 5–7 gün. **Bağımlılık:** statsmodels; PH testi ve konkordans için
lifelines (opsiyonel grup; yoksa yöntem listede çıkmaz ve hangi grubun eksik
olduğu yazılır — Cohort-Studio'nun zarif bozulma kuralı).

**Doğrula.** `biostats` referans değerleri + bir yayınlanmış kohort verisiyle
bilinen HR/AUC. `test_cohort_survival.py`.

---

### ✅ Faz 6 — Eksik veri: MCAR + multiple imputation + Rubin

**Problem.** Gözlemsel kohortlarda eksik veri kuraldır; complete-case analiz
yanlı. Ama **yanlış yapılmış MI, tek imputasyondan daha kötüdür** — çünkü
belirsizliği yaydığını iddia ederken yaymaz.

**Yapılacak.**
- `method=mcar` (Little's test, EM).
- `method=mi` → `gazzali/cohort/vendor/biostats/mi/` (chained equations,
  PMM/bayes/logit/polytomous/RF donör; m bağımsız zincir; R-hat, trace,
  gözlenen-vs-impute tanıları).
- `method=mi_pool` → Rubin kuralları, Barnard-Rubin df, D1/D2 testleri,
  log/logit/cloglog ölçekleri. Her zaman yanında **complete-case** kolonu.
- **Sert kural:** tek imputasyon asla çıkarım için sunulmaz. Kullanılırsa her
  sonuçta "bu sonuç tek imputasyon kullanır, standart hatalar küçüktür" uyarısı
  görünür (Cohort-Studio'nun en doğru kararı; aynen koruyoruz).
- Dışa aktarım: R `mice` (long) ve Stata (`flong`) — biyoistatistikçiyle
  işbirliği için.

**Efor.** 6–10 gün (vendor sayesinde; sıfırdan yazılsa 25+).
**Doğrulama şartı:** `tests/reference/fixtures/mi/` ile R `mice` 3.19 / `mitml`
0.4.5 paritesi **1e-10**. Bu fixture'lar taşınmadan faz kapanmaz.

---

### 🟢 Faz 7 — Study dossier ve rapor

**Problem.** Hoca makaleyi yazarken yöntem/akış/eksik veri paragraflarını elle
topluyor; sayılar kayıyor.

**Yapılacak.**
- `GET /cohort/tables/{id}/dossier` → `.docx` (`python-docx`): provenans,
  participant flow figürü, veri işleme, eksik veri (Sterne 2009 maddeleri),
  seçilmiş sonuçlar, kaynakça (`biostats/references.py`).
- Sonuç kartındaki "dossier'e ekle" düğmesi (`study_dossier` deseni).
- Popülasyon/veri değişmiş sonuçlar dossier'e **girmez**; istenirse işaretli girer.
- Zorunlu ibare: *"Bu belge bir uyumluluk sertifikası veya elektronik imzalı
  kayıt değildir."* — Cohort-Studio'nun dürüstlüğü; aynen alın.
- Başlangıç için mevcut HTML→`.doc` hattı yeterli; `.docx` ikinci adım.

**Efor.** 4–5 gün. **Bağımlılık:** python-docx (worker'da).

---

## 6. Şema önerisi

```sql
-- Bir analiz edilen tablo; yönetişimdeki dataset'e (varsa) bağlı.
CREATE TABLE IF NOT EXISTS cohort_tables (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    dataset_id      TEXT REFERENCES datasets(id) ON DELETE RESTRICT,
    lab_id          TEXT NOT NULL REFERENCES labs(id) ON DELETE RESTRICT,
    name            TEXT NOT NULL,
    dictionary_json TEXT NOT NULL DEFAULT '{}',
    config_json     TEXT NOT NULL DEFAULT '{}',   -- criteria families
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL,
    UNIQUE(project_id, name)
);

-- Değişmez sürüm; dosya Garage'ta, üst veri burada.
CREATE TABLE IF NOT EXISTS cohort_versions (
    id               TEXT PRIMARY KEY,
    table_id         TEXT NOT NULL REFERENCES cohort_tables(id) ON DELETE CASCADE,
    version_no       INTEGER NOT NULL,
    s3_key           TEXT NOT NULL,
    rows             INTEGER NOT NULL,
    columns_json     TEXT NOT NULL,
    content_sha256   TEXT NOT NULL,
    parent_version_id TEXT REFERENCES cohort_versions(id),
    parse_report_json TEXT,
    created_by       TEXT NOT NULL REFERENCES users(id),
    created_at       TEXT NOT NULL,
    UNIQUE(table_id, version_no)
);

-- İlan edilmiş analiz popülasyonu + flow aşamaları + parmak izi.
CREATE TABLE IF NOT EXISTS cohort_populations (
    id           TEXT PRIMARY KEY,
    version_id   TEXT NOT NULL REFERENCES cohort_versions(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    criteria_json TEXT NOT NULL,
    stages_json  TEXT NOT NULL,
    n_in         INTEGER NOT NULL,
    n_out        INTEGER NOT NULL,
    fingerprint  TEXT NOT NULL,
    created_by   TEXT NOT NULL REFERENCES users(id),
    created_at   TEXT NOT NULL
);

-- Hash-zincirli veri soy kütüğü (audit_log'dan ayrı: bu satır verisi konuşur).
CREATE TABLE IF NOT EXISTS cohort_steps (
    id            TEXT PRIMARY KEY,
    version_id    TEXT NOT NULL REFERENCES cohort_versions(id) ON DELETE CASCADE,
    seq           INTEGER NOT NULL,
    kind          TEXT NOT NULL
                  CHECK(kind IN ('import','derive','filter','impute','clip','convert','merge')),
    params_json   TEXT NOT NULL,
    out_version_id TEXT REFERENCES cohort_versions(id),
    prev_hash     TEXT NOT NULL,
    hash          TEXT NOT NULL,
    created_by    TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at    TEXT NOT NULL,
    UNIQUE(version_id, seq)
);

-- Hesaplanmış bir analiz; popülasyon parmak izine bağlı.
CREATE TABLE IF NOT EXISTS cohort_analyses (
    id                    TEXT PRIMARY KEY,
    population_id         TEXT NOT NULL REFERENCES cohort_populations(id) ON DELETE CASCADE,
    method                TEXT NOT NULL,
    params_json           TEXT NOT NULL,
    result_json           TEXT NOT NULL,
    n                     INTEGER NOT NULL,
    engine_version        TEXT NOT NULL,
    population_fingerprint TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'current'
                          CHECK(status IN ('current','stale','failed')),
    job_id                TEXT,
    error                 TEXT,
    created_by            TEXT NOT NULL REFERENCES users(id),
    created_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cohort_analyses_pop ON cohort_analyses(population_id);

-- Doğrulanabilir tekil sayılar (dossier ve metrik köprüsü bunu okur).
CREATE TABLE IF NOT EXISTS cohort_analysis_values (
    analysis_id TEXT NOT NULL REFERENCES cohort_analyses(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    value       REAL NOT NULL,
    unit        TEXT,
    ci_low      REAL,
    ci_high     REAL,
    p_value     REAL,
    n           INTEGER,
    PRIMARY KEY (analysis_id, name)
);
```

Mevcut tabloya tek ekleme:

```sql
-- migration: kohort sonucundan gelen metriği geri izlenebilir yap
ALTER TABLE experiment_metrics ADD COLUMN source_analysis_id TEXT;
```

---

## 7. Bağımlılık ve dağıtım

| Nereye | Ne | Not |
|---|---|---|
| `gazzali-analysis` worker | pandas, pyarrow, duckdb, scipy, statsmodels, numpy | Ayrı imaj; ana API imajı büyümez |
| opsiyonel | lifelines (Faz 5 PH/konkordans), scikit-learn (IF/LOF/DBSCAN, RF donör), python-docx (Faz 7) | Yoksa yöntem listede çıkmaz + eksik grup söylenir |
| ana API | **hiçbiri** | Istatistik API sürecinde koşmaz |

`deploy/docker-compose.prod.yml`'e `analysis` servisi: internal, CPU limiti,
egress yok, `ANALYSIS_WORKER_URL` + `ANALYSIS_WORKER_TOKEN`. `researchclaw`
servisiyle aynı desen, ayrı kimlik.

`SystemHealthPage`'e "analysis engine: sürüm / kurulu yöntemler" satırı.

---

## 8. Riskler ve dürüstlük kuralları

1. **Yanlış MI, hiç MI'dan kötüdür.** Faz 6, R parite fixture'ları olmadan
   kapanmaz. Bu fazı acele ettirmeyin; gerekirse hiç yapmayın.
2. **"İstatistik" bir özellik değil, bir sorumluluktur.** Modül p-değeri
   ürettiği anda akademik iddia üretir. Varsayım kontrolleri **tanı**, kapı
   değil; ama sonuç kartı hangi testin neden seçildiğini yazmalı.
3. **AI hiçbir formülü/analizi otomatik uygulamasın.** Öneri → önizleme →
   onay. Gazzali'nin `verify_numbers` etiğiyle tutarlı olan tek yol bu.
4. **Bayat sonuç sessizce geçerli kalmamalı.** Faz 4 bunun için var; atlanırsa
   modül güven kaybeder.
5. **Hasta verisi.** `cohort_tables.dataset_id` zorunlu tutulmalı; analiz
   deid'den geçmiş sürüm üzerinde koşmalı; IRB süresi dolmuşsa erişim kapalı.
   KVKK açısından veri yurt dışına çıkmamalı → worker local, LLM local.
6. **Lisans/atıf.** Apache-2.0: `NOTICE`, dosya başlıkları, yöntem atıfları
   korunur. Üniversite ürününde bu denetlenebilir olmalı.
7. **Kapsam kayması.** 14 grafik, bilgi grafiği, variable map, RAG bu modülün
   işi değil. Faz 3'ün Tablo 1'i + Faz 5'in 3 grafiği yeter.

---

## 9. Yapılmayacaklar (bilinçli)

- Streamlit, DuckDB deposu, kullanıcı başına workspace, kendi IAM'i.
- Tüm `app_pages/` grafik galerisi — bizde matplotlib hattı var.
- Bilgi grafiği / variable map / doküman RAG — copilot zaten var.
- yFiles tescilli render.
- Cohort-Studio'nun 800 testlik kapsama tabanı — bizde `biostats` fixture'ları
  + modül başına API testi yeterli.
- Ayrı bir "istatistikçi rolü" — mevcut lab/proje RBAC'i yeterli.

---

## 10. ARC ile ilişkisi (karıştırılmasın)

| | Cohort modülü | AutoResearchClaw |
|---|---|---|
| Girdi | IRB onaylı kohort verisi | Konu/fikir |
| Kontrol | Araştırmacı her adımı seçer ve görür | Ajan ilerler, insan kapılarda onaylar |
| Çıktı | Tablo 1, flow, HR/OR, dossier | Deney hattı, metrik, ders |
| Soru | "Bu veri ne diyor?" | "Bu fikri deneyebilir miyiz?" |

İkisi birleşir: ARC `medical_observational` profilinde ürettiği veri işleme
adımlarını cohort modülüne devredebilir; cohort modülünün `publish` ettiği
metrikler ARC'nin `VerifiedRegistry`'sine düşer. Ama **iki ayrı ürün yüzeyi**
olarak kalmalı.

---

## 11. Açık sorular

1. **Kapsam:** İlk sürüm sadece Faz 1–2 (popülasyon + flow + kalite) mi olsun,
   yoksa Faz 3 (Tablo 1) ile birlikte mi çıksın? *Önerim: 1–2–4 birlikte;
   provenans olmadan analiz yayınlamak risklidir.*
2. **Veri hacmi:** Tipik kohort kaç satır/sütun? 100k satır altıysa DuckDB
   gerekmez, pandas yeter ve worker daha basit olur.
3. **Vendor onayı:** `core/` + `biostats/` kodu doğrudan vendor'lansın mı,
   yoksa `git subtree`/ayrı paket olarak mı izlensin? *Önerim: `cohort/vendor/`
   + `NOTICE` + sürüm notu; upstream güncellemesi elle, seyrek.*
4. **Hasta verisi politikası:** Analiz gerçekten IRB'li hasta verisi üzerinde mi
   koşacak, yoksa ilk aşamada yalnızca sentetik/public kohortlarda mı?
   (ARC için de aynı soru açıkta — `plan/autoresearchclaw-integration.md` §4.)
5. **İlk hedef kullanıcı:** Tıp fakültesi hocası mı (Tablo 1 + dossier), yoksa
   biyoistatistikçi mi (R export, MI tanıları)? Arayüz önceliği buna göre değişir.
6. **Dil:** Dossier ve arayüz Türkçe mi İngilizce mi? (Makale İngilizce,
   arayüz Türkçe olabilir — ama dossier iki dilli olmalı gibi görünüyor.)

---

## 12. Kaynaklar

- [Cohort-Studio](https://github.com/KarimELMERNISSI/Cohort-Studio) · Apache-2.0 · DOI [10.5281/zenodo.23436094](https://doi.org/10.5281/zenodo.23436094)
- STROBE — von Elm et al. 2007, madde 13 (participant flow)
- Eksik veri raporlaması — Sterne et al. 2009, BMJ
- Rubin kuralları — Rubin 1987; Barnard & Rubin 1999; R `mice` 3.19, `mitml` 0.4.5
- Little's MCAR — Little 1988
- Etki büyüklüğü GA — Steiger 2004 (noncentral t)
- `documentation/08_Reproduction.md`, `documentation/02_Data_Validation.md` (kaynak projede)
