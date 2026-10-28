        if (window.lucide) window.lucide.createIcons();

        // 1..14 NUMARALI MANŞET SLIDER ENGINE (TOUCH SWIPE & MOUSE DRAG DESTEKLİ)
        (function() {
            const slides = document.querySelectorAll('.manset-slide');
            const pills = document.querySelectorAll('.manset-pill');
            if (slides.length <= 1) return;

            let curIndex = 0;
            const total = slides.length;
            let autoTimer = null;

            function showSlide(idx) {
                if (idx < 0) idx = total - 1;
                if (idx >= total) idx = 0;
                curIndex = idx;

                slides.forEach((s, i) => {
                    if (i === curIndex) {
                        s.classList.remove('opacity-0', 'pointer-events-none', 'z-0');
                        s.classList.add('opacity-100', 'pointer-events-auto', 'z-10');
                    } else {
                        s.classList.remove('opacity-100', 'pointer-events-auto', 'z-10');
                        s.classList.add('opacity-0', 'pointer-events-none', 'z-0');
                    }
                });

                pills.forEach((p, i) => {
                    if (i === curIndex) {
                        p.className = 'manset-pill flex-1 min-w-[28px] sm:min-w-[34px] py-1.5 rounded-lg text-xs sm:text-sm font-extrabold text-center transition-all duration-200 shadow-sm bg-red-600 text-white scale-105 shadow-red-900/50';
                    } else {
                        p.className = 'manset-pill flex-1 min-w-[28px] sm:min-w-[34px] py-1.5 rounded-lg text-xs sm:text-sm font-extrabold text-center transition-all duration-200 shadow-sm bg-slate-900/90 text-slate-300 hover:bg-slate-800 hover:text-white border border-slate-800';
                    }
                });
            }

            function startAuto() {
                stopAuto();
                autoTimer = setInterval(() => {
                    showSlide(curIndex + 1);
                }, 4000);
            }

            function stopAuto() {
                if (autoTimer) {
                    clearInterval(autoTimer);
                    autoTimer = null;
                }
            }

            window.goToManset = function(idx) {
                showSlide(idx);
                startAuto();
            };

            window.moveManset = function(step) {
                showSlide(curIndex + step);
                startAuto();
            };

            // Touch Swipe & Mouse Drag
            const sliderBox = document.getElementById('main-manset-slider');
            if (sliderBox) {
                let isMouseDown = false;
                let mouseStartX = 0;
                let mouseDiffX = 0;
                let dragged = false;

                sliderBox.addEventListener('mouseenter', () => { if (!isMouseDown) stopAuto(); });
                sliderBox.addEventListener('mouseleave', () => { if (!isMouseDown) startAuto(); });

                // Dokunmatik (Mobil / Tablet)
                let touchStartX = 0;
                let touchStartY = 0;
                let touchDiffX = 0;
                let touchDiffY = 0;

                sliderBox.addEventListener('touchstart', (e) => {
                    stopAuto();
                    touchStartX = e.changedTouches[0].clientX;
                    touchStartY = e.changedTouches[0].clientY;
                    touchDiffX = 0;
                    touchDiffY = 0;
                }, { passive: true });

                sliderBox.addEventListener('touchmove', (e) => {
                    touchDiffX = e.changedTouches[0].clientX - touchStartX;
                    touchDiffY = e.changedTouches[0].clientY - touchStartY;
                }, { passive: true });

                sliderBox.addEventListener('touchend', () => {
                    if (Math.abs(touchDiffX) > 35 && Math.abs(touchDiffX) > Math.abs(touchDiffY)) {
                        if (touchDiffX < 0) {
                            showSlide(curIndex + 1);
                        } else {
                            showSlide(curIndex - 1);
                        }
                    }
                    startAuto();
                }, { passive: true });

                // PC Fare ile Sürükleme
                sliderBox.addEventListener('mousedown', (e) => {
                    isMouseDown = true;
                    dragged = false;
                    mouseStartX = e.clientX;
                    mouseDiffX = 0;
                    stopAuto();
                });

                window.addEventListener('mousemove', (e) => {
                    if (!isMouseDown) return;
                    mouseDiffX = e.clientX - mouseStartX;
                    if (Math.abs(mouseDiffX) > 10) dragged = true;
                });

                window.addEventListener('mouseup', () => {
                    if (!isMouseDown) return;
                    isMouseDown = false;
                    if (Math.abs(mouseDiffX) > 40) {
                        if (mouseDiffX < 0) showSlide(curIndex + 1);
                        else showSlide(curIndex - 1);
                    }
                    startAuto();
                });

                sliderBox.addEventListener('click', (e) => {
                    if (dragged) {
                        e.preventDefault();
                        e.stopPropagation();
                        dragged = false;
                    }
                }, true);
            }

            startAuto();
        })();

                // =====================================================================
        // 1. BULLETPROOF GLOBAL MODAL ENGINE (SAFE, RE-ENTRANT, ZERO-DEPENDENCY)
        // =====================================================================
        function openModal(id) {
            var el = document.getElementById(id);
            if (el) {
                el.classList.remove('hidden');
                el.style.setProperty('display', 'flex', 'important');
                document.body.style.overflow = 'hidden';
            }
        }
        function closeModal(id) {
            var el = document.getElementById(id);
            if (el) {
                el.classList.add('hidden');
                el.style.setProperty('display', 'none', 'important');
                document.body.style.overflow = '';
            }
        }
        window.openModal = openModal;
        window.closeModal = closeModal;

        // Modal Kısayolları (Tüm Cihazlar İçin Güvenli)
        var _namazInitialized = false;
        function openNamazModal() {
            openModal('namaz-modal');
            if (!_namazInitialized) {
                _namazInitialized = true;
                try {
                    populateNamazCities();
                    updateNamazModal('İstanbul');
                    startPrayerCountdown();
                } catch(e) {}
            }
        }
        function closeNamazModal() { closeModal('namaz-modal'); }

        var _nobetciInitialized = false;
        function openNobetciModal() {
            openModal('nobetci-modal');
            if (!_nobetciInitialized) {
                _nobetciInitialized = true;
                try {
                    populateNobetciCities();
                    loadNobetciCity('İstanbul');
                } catch(e) {}
            }
        }
        function closeNobetciModal() { closeModal('nobetci-modal'); }

        var _depremInitialized = false;
        function openDepremModal() {
            openModal('deprem-modal');
            if (!_depremInitialized) {
                _depremInitialized = true;
                try {
                    renderDepremList(SAMPLE_QUAKES);
                } catch(e) {}
            }
            try { fetchLiveDeprem(); } catch(e) {}
        }
        function closeDepremModal() { closeModal('deprem-modal'); }
        function openIhbarModal() { openModal('ihbar-modal'); }
        function closeIhbarModal() { closeModal('ihbar-modal'); }

        async function submitIhbarForm(e) {
            e.preventDefault();
            const btn = document.getElementById('ih-submit');
            const st = document.getElementById('ih-status');
            const msgInput = document.getElementById('ih-msg');
            if (!msgInput || !msgInput.value.trim()) return;

            btn.disabled = true;
            btn.innerHTML = '<span>⏳ Gönderiliyor...</span>';
            st.className = 'hidden';

            const fd = new FormData();
            fd.append('message', msgInput.value.trim());
            fd.append('contact', (document.getElementById('ih-contact')?.value || '').trim());
            const fInput = document.getElementById('ih-file');
            if (fInput && fInput.files && fInput.files.length > 0) {
                fd.append('media_file', fInput.files[0]);
            }

            try {
                const res = await fetch('/api/ihbar', { method: 'POST', body: fd });
                const data = await res.json();
                st.classList.remove('hidden');
                if (res.ok && data.ok) {
                    st.className = 'p-3 rounded-xl text-xs font-bold text-center bg-emerald-950 text-emerald-300 border border-emerald-500/40';
                    st.innerText = '✅ ' + (data.message || 'İhbarınız haber merkezimize başarıyla iletildi!');
                    document.getElementById('ihbar-form').reset();
                    setTimeout(() => closeIhbarModal(), 2500);
                } else {
                    st.className = 'p-3 rounded-xl text-xs font-bold text-center bg-red-950 text-red-300 border border-red-500/40';
                    st.innerText = '⚠️ ' + (data.detail || 'Bir hata oluştu, lütfen tekrar deneyin.');
                }
            } catch (err) {
                st.classList.remove('hidden');
                st.className = 'p-3 rounded-xl text-xs font-bold text-center bg-red-950 text-red-300 border border-red-500/40';
                st.innerText = '⚠️ Bağlantı hatası oluştu. Lütfen tekrar deneyin.';
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<span>🚀 İhbarı Gönder</span>';
            }
        }
        window.submitIhbarForm = submitIhbarForm;
        function openA11yModal() { openModal('a11y-modal-backdrop'); }
        function closeA11yModal() { closeModal('a11y-modal-backdrop'); }

        window.openNamazModal = openNamazModal;
        window.closeNamazModal = closeNamazModal;
        window.openNobetciModal = openNobetciModal;
        window.closeNobetciModal = closeNobetciModal;
        window.openDepremModal = openDepremModal;
        window.closeDepremModal = closeDepremModal;
        window.openIhbarModal = openIhbarModal;
        window.closeIhbarModal = closeIhbarModal;
        window.openA11yModal = openA11yModal;
        window.closeA11yModal = closeA11yModal;

        // ESC Tuşuyla Tüm Modalları Kapat
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                ['search-modal', 'namaz-modal', 'nobetci-modal', 'deprem-modal', 'ihbar-modal', 'astro-modal', 'a11y-modal-backdrop'].forEach(function(id) {
                    closeModal(id);
                });
            }
        });

        // =====================================================================
        // 2. 12 BURÇ YAPAY ZEKA GÜNLÜK YORUM MOTORU (OTOMATİK GÜNLÜK YORUM)
        // =====================================================================
        // =====================================================================
        // 🔮 1. 99 LVL ASTROLOJİ & BURÇLAR MERKEZİ (HÜRRİYET STANDARDI MOTORU)
        // =====================================================================
        var currentAstroSign = 'Koç';
        var currentAstroPeriod = 'bugun';

        var ZODIAC_99LVL_DATA = {
            'Koç': {
                symbol: '♈',
                dates: '21 Mart - 20 Nisan',
                motto: '"Yeter ki hevesim kırılmasın, başladığım işi fethederim!"',
                planet: 'Mars',
                element: 'Ateş',
                quality: 'Öncü',
                stone: 'Pırlanta / Akik (Salı)',
                luckyNum: '7 & 9',
                luckyColor: 'Canlı Kırmızı & Mercan',
                bugun: {
                    general: 'Bugün gökyüzünde Mars ve Ay uyumu liderlik dürtülerinizi tetikliyor. Ertelediğiniz projelere başlamak ve inisiyatif almak için kusursuz bir gün. Çevrenize ilham verecek, kararlı duruşunuzla engelleri tek tek aşacaksınız.',
                    love: 'Aşk hayatınızda açık ve dobra iletişim rüzgarları esiyor. Partnerinizle aranızdaki küçük kırgınlıkları tatlıya bağlayabilir, bekarsanız heyecan verici ve enerjik bir tanışma yaşayabilirsiniz.',
                    money: 'Finansal alanda cesur adımlar atmak isteseniz de ani harcamalardan kaçınmalı, bütçe dengenizi koruyarak stratejik hareket etmelisiniz.',
                    health: 'Fiziksel enerjiniz oldukça yüksek. Açık hava yürüyüşleri, tempolu kardiyo veya spor seansları zihninizi deha gibi boşaltacaktır.'
                },
                dun: {
                    general: 'Dün yaşadığınız koşturmaca ve zihinsel yoğunluk yerini daha berrak bir farkındalığa bırakıyor. Dün aldığınız kararların meyvelerini toplamaya başlıyorsunuz.',
                    love: 'Partnerinizle dünkü konuşmaların ardından duygusal zemini sağlamlaştırdınız.',
                    money: 'Ödemeler ve fatura dengesi konusunda dün planladığınız tablo rahat nefes aldırıyor.',
                    health: 'Baş ve boyun bölgesindeki gerginlik dünkü dinlenmeyle birlikte dağıldı.'
                },
                yarin: {
                    general: 'Yarın yeni bir sorumluluk veya iş birliği kapınızı çalabilir. Kararlılığınızı koruyun, sezgilerinize güvenerek ilk adımı atın.',
                    love: 'Romantik jestler ve sürpriz planlar için harika bir enerji alanı oluşacak.',
                    money: 'Kariyerinizde takdir toplayacağınız yeni bir proje veya gelir fırsatı belirebilir.',
                    health: 'Enerjinizi dengeli harcamaya özen gösterin, uykunuzu aksatmayın.'
                },
                haftalik: {
                    general: 'Bu hafta iş ve özel yaşam dengesini kurma haftası. Mars retrosu öncesinde önemli görüşmelerinizi tamamlamalı, hedeflerinize kilitlenmelisiniz.',
                    love: 'İlişkilerde dürüstlük ve tutku ön planda. Güven tazelemek ilişkinizi bir üst seviyeye taşıyacak.',
                    money: 'Girişimci yönünüz tavan yapıyor. Yeni yatırımlar için doğru insanlarla bir araya gelebilirsiniz.',
                    health: 'Kas ağrılarına karşı esneme egzersizlerini ve su tüketimini ihmal etmeyin.'
                },
                aylik: {
                    general: 'Bu ay kariyerinizde dönüm noktası oluşturacak gelişmeler yaşanabilir. Gökyüzü cesaretinizi ödüllendiriyor. Yeni hedeflere yelken açma zamanı!',
                    love: 'Uzun vadeli kararlar, nişan, evlilik veya ortak bir yaşam adımı gündeme gelebilir.',
                    money: 'Maddi konularda uzun süredir beklediğiniz bir alacak tahsil edilebilir.',
                    health: 'Ruhsal ve bedensel detoks için mükemmel bir ay. Fazlalıklardan arının.'
                }
            },
            'Boğa': {
                symbol: '♉',
                dates: '21 Nisan - 20 Mayıs',
                motto: '"Huzur, güven ve sağlam temeller hayattaki en büyük kalendir."',
                planet: 'Venüs',
                element: 'Toprak',
                quality: 'Sabit',
                stone: 'Zümrüt / Turkuaz (Cuma)',
                luckyNum: '6 & 15',
                luckyColor: 'Zümrüt Yeşili & Toprak Tonları',
                bugun: {
                    general: 'Venüs etkisiyle bugün estetik, konfor ve huzur arayışınız ön planda. Çalışma ortamınızı veya evinizi güzelleştirebilir, keyifli lezzetlerle kendinizi ödüllendirebilirsiniz.',
                    love: 'İlişkinizde güven ve şefkat rüzgarları esiyor. Partnerinizle birlikte geçireceğiniz sakin bir akşam bağı güçlendirecektir.',
                    money: 'Maddi konularda oldukça sağlam ve basiretli adımlar atıyorsunuz. Tasarruf ve uzun vadeli birikim planlarınız meyvesini veriyor.',
                    health: 'Boğaz bölgenizi ve boyun kaslarınızı koruyun. Sıcak bitki çayları ve hafif esneme hareketleri iyi gelecektir.'
                },
                dun: {
                    general: 'Dünkü belirsizlikler ve küçük pürüzler bugün yerini tam bir netliğe bıraktı. Sabırlı tavrınız kazandırdı.',
                    love: 'Dün yaşanan duygusal yakınlaşma aranızdaki bağı daha da pekiştirdi.',
                    money: 'Bütçenizi dün gözden geçirmiş olmanız gereksiz masrafları önledi.',
                    health: 'Uyku kalitenizi artırarak güne çok daha dinç başladınız.'
                },
                yarin: {
                    general: 'Yarın iş yerinde veya hanede kalıcı bir düzen kurmak için fırsat bulacaksınız. Pratik zekanız herkesi hayran bırakacak.',
                    love: 'Aşkta samimi itiraflar ve güven dolu adımlar söz konusu.',
                    money: 'Kalıcı ve güvenli yatırım araçları hakkında yeni araştırmalar yapabilirsiniz.',
                    health: 'Beslenmenizde şeker ve ağır yiyecekleri sınırlandırmayı deneyin.'
                },
                haftalik: {
                    general: 'Hafta boyunca finansal güvenlik ve aile içi huzur ana temanız olacak. Kararlı ve sakin duruşunuz krizleri fırsata çevirecek.',
                    love: 'Sadakat ve sevgi dolu anlar ilişkinize istikrar katıyor.',
                    money: 'Beklenmedik bir prim, zam veya ek kazanç imkanı doğabilir.',
                    health: 'Bedeninizin dinlenme sinyallerini dikkate alın, doğayla temas edin.'
                },
                aylik: {
                    general: 'Bu ay gayrimenkul, ev değişimi veya kariyerde kalıcı terfi haberleri kapınızı çalabilir. İstikrarınızın meyvelerini topluyorsunuz.',
                    love: 'Aşk hayatınızda kalıcı ve ciddiyet dolu temeller atılacak.',
                    money: 'Maddi anlamda en bereketli ve kazançlı dönemlerinizden biri başlıyor.',
                    health: 'Beden ağırlığınızı dengede tutacak taze gıdalara yönelin.'
                }
            },
            'İkizler': {
                symbol: '♊',
                dates: '21 Mayıs - 21 Haziran',
                motto: '"Merak etmediğim gün, gerçekten yaşamadığım gündür!"',
                planet: 'Merkür',
                element: 'Hava',
                quality: 'Değişken',
                stone: 'Akik / Kehribar (Çarşamba)',
                luckyNum: '5 & 14',
                luckyColor: 'Sarı & Parlak Gümüş',
                bugun: {
                    general: 'Merkür zihninizi ışık hızında çalıştırıyor. İletişim, toplantılar, yeni fikirler ve sosyal bağlantılar bugün zirvede. Çözülmez sanılan düğümleri pratik zekanızla çözeceksiniz.',
                    love: 'Zihinsel çekim ve espritüel sohbetler aşk kapınızı aralıyor. Partnerinizle doyumsuz sohbetler edebilirsiniz.',
                    money: 'Dijital işler, ticaret veya satış konularında karlı anlaşmalar yapabilirsiniz.',
                    health: 'Zihniniz çok hareketli olduğu için akşam saatlerinde ekran süresini azaltıp dinlenmeye odaklanmalısınız.'
                },
                dun: {
                    general: 'Dün aldığınız bir haber veya kurduğunuz bir diyalog bugün yeni kapılar açıyor.',
                    love: 'Dünkü esprili yaklaşımınız partnerinizin gönlünü fethetti.',
                    money: 'Hızlı bir nakit akışı dün planladığınız alımı kolaylaştırdı.',
                    health: 'Zihinsel yorgunluğu yürüyüşle hafiflettiniz.'
                },
                yarin: {
                    general: 'Yarın yeni bir eğitim, seyahat veya iş teklifi gündeminize bomba gibi düşebilir.',
                    love: 'Sosyal çevrenizden biriyle aranızda tatlı bir elektriklenme oluşabilir.',
                    money: 'İkna kabiliyetiniz sayesinde önemli bir anlaşmayı lehinize çevirebilirsiniz.',
                    health: 'Nefes egzersizleri ve temiz hava ciğerlerinize çok iyi gelecek.'
                },
                haftalik: {
                    general: 'Hafta boyunca çok yönlü işler ve yoğun bir iletişim trafiği sizi bekliyor. Sosyal çevreniz genişliyor.',
                    love: 'Farklı bakış açıları ilişkinize dinamizm katacak.',
                    money: 'Teknoloji, medya veya danışmanlık projelerinden gelir elde edebilirsiniz.',
                    health: 'Eller ve omuz bölgesindeki tutulmalara karşı esneme yapın.'
                },
                aylik: {
                    general: 'Bu ay yeni bir sözleşme, seyahat veya eğitim fırsatı hayatınızın akışını hızlandıracak. Değişime kucak açın!',
                    love: 'Sürpriz bir aşk ilanı veya var olan ilişkide yeni bir vizyon sizi bekliyor.',
                    money: 'Yaratıcı fikirleriniz nakde dönüyor.',
                    health: 'Zihninizi meditasyon veya kitap okuyarak dinlendirin.'
                }
            },
            'Yengeç': {
                symbol: '♋',
                dates: '22 Haziran - 22 Temmuz',
                motto: '"Sevgiyle koruduğum yuvam, benim en güçlü sığınağımdır."',
                planet: 'Ay',
                element: 'Su',
                quality: 'Öncü',
                stone: 'Aytaşı / İnci (Pazartesi)',
                luckyNum: '2 & 11',
                luckyColor: 'Beyaz & Gümüş Sedef',
                bugun: {
                    general: 'Ay enerjisi sezgilerinizi en üst seviyeye taşıyor. Kalbinizin sesini dinleyerek aldığınız kararlar sizi asla yanıltmayacak. Aileniz ve sevdiklerinizle sıcacık paylaşımlar yaşayacaksınız.',
                    love: 'Derin duygular, şefkat ve koruyucu enerji ön planda. Sevdiğiniz kişiye hislerinizi açmaktan çekinmeyin.',
                    money: 'Ev ve aileyle ilgili harcamalar gündeme gelse de bütçeniz sağlam duruyor.',
                    health: 'Mide hassasiyetine dikkat. Doğal, taze ve hafif ev yemekleri tüketmeye özen gösterin.'
                },
                dun: {
                    general: 'Dünkü duygusal dalgalanmalar yerini iç huzura ve dinginliğe bıraktı.',
                    love: 'Partnerinizin dün gösterdiği ilgi kalbinizi ısıttı.',
                    money: 'Dün yaptığınız tasarruflu hamle bütçenizi rahatlattı.',
                    health: 'Ilık bir duş ve erken uyku dünün yorgunluğunu sildi.'
                },
                yarin: {
                    general: 'Yarın evinizde veya işinizde konfor alanı yaratacak adımlar atacaksınız.',
                    love: 'Romantik ve nostaljik bir buluşma gündeme gelebilir.',
                    money: 'Birikimlerinizi güvenceye alacak yeni bir plan yapabilirsiniz.',
                    health: 'Bol su tüketimi sindirim sisteminizi rahatlatacaktır.'
                },
                haftalik: {
                    general: 'Hafta boyunca sezgileriniz size rehberlik edecek. Sevdiklerinizle bir araya gelmek ruhunuzu besleyecek.',
                    love: 'Duygusal bağlar derinleşiyor, kalpler aynı frekansta atıyor.',
                    money: 'Aile destekli bir maddi konu veya miras/tapu işi çözüme kavuşabilir.',
                    health: 'Duygusal yeme krizlerine karşı bitki çaylarına yönelin.'
                },
                aylik: {
                    general: 'Bu ay kariyerinizde saygınlık kazanacağınız ve hanenizde büyük bir müjdenin kutlanacağı bereketli bir dönem.',
                    love: 'İlişkinizde güven çıtası en tepeye çıkıyor.',
                    money: 'Uzun vadeli yatırımlarınız değer kazanacak.',
                    health: 'Bağışıklığınızı güçlendirecek vitamin takviyeleri alın.'
                }
            },
            'Aslan': {
                symbol: '♌',
                dates: '23 Temmuz - 22 Ağustos',
                motto: '"Işığın olduğu yerde parlarım, karanlığa ise ışık olurum!"',
                planet: 'Güneş',
                element: 'Ateş',
                quality: 'Sabit',
                stone: 'Yakut / Kehribar (Pazar)',
                luckyNum: '1 & 10',
                luckyColor: 'Altın Sarısı & Kraliyet Turuncusu',
                bugun: {
                    general: 'Güneş yönetiminizdeki karizmanız bugün çevrenizdeki herkesi büyülüyor. Girdiğiniz her ortamda liderliğinizle dikkat çekecek, projelerinizi alkışlarla kabul ettireceksiniz.',
                    love: 'Tutkulu, cömert ve coşkulu bir aşk enerjisi hakim. Partnerinize yapacağınız jestler unutulmaz anlar yaratacak.',
                    money: 'Kariyerinizde terfi veya kazanç artırıcı görüşmeler için son derece şanslı bir gün.',
                    health: 'Kalp ve sırt sağlığınızı destekleyin; dik duruş egzersizleri ve yürüyüş yapın.'
                },
                dun: {
                    general: 'Dün ortaya koyduğunuz iddia bugün haklılığınızı kanıtladı.',
                    love: 'Dünkü cömert tavrınız partnerinizi büyüledi.',
                    money: 'Kariyerde dün attığınız tohumlar bugün filizleniyor.',
                    health: 'Günün enerjisini sporla destekleyerek formunuzu korudunuz.'
                },
                yarin: {
                    general: 'Yarın yeni bir sahneye çıkacak ve yeteneklerinizi sergileme fırsatı bulacaksınız.',
                    love: 'Övgü dolu sözler ve romantik kıvılcımlar havada uçuşacak.',
                    money: 'Lüks harcamalarda ölçüyü kaçırmamaya dikkat edin.',
                    health: 'Güneş ışığından faydalanın, D vitamini enerjinizi katlayacaktır.'
                },
                haftalik: {
                    general: 'Hafta boyunca popülariteniz zirvede olacak. Çevrenizdekiler fikirlerinize ve vizyonunuza başvuracak.',
                    love: 'Aşkta krallara layık bir ilgi ve heyecan dolu günler kapıda.',
                    money: 'Yeni iş teklifleri veya ortaklıklar maddi kazancınızı artıracak.',
                    health: 'Aşırı stresten kaçının, kalbinizi yormayacak hafif tempolu sporlar yapın.'
                },
                aylik: {
                    general: 'Bu ay kariyerinizde adeta altın çağınızı başlatacak gelişmeler yaşanabilir. Başarı basamaklarını hızla tırmanacaksınız.',
                    love: 'Bekarsanız çevrenizden herkesi kıskandıracak bir aşk başlayabilir.',
                    money: 'Yatırımlarınızdan yüksek getiri elde edeceksiniz.',
                    health: 'Canlılığınız ve direnciniz yüksek olacak.'
                }
            },
            'Başak': {
                symbol: '♍',
                dates: '23 Ağustos - 22 Eylül',
                motto: '"Kusursuzluk ayrıntılarda gizlidir, düzen ise huzurun anahtarıdır."',
                planet: 'Merkür',
                element: 'Toprak',
                quality: 'Değişken',
                stone: 'Akik / Safir (Çarşamba)',
                luckyNum: '5 & 23',
                luckyColor: 'Lacivert & Açık Gri',
                bugun: {
                    general: 'Analitik zekanız ve organizasyon beceriniz bugün en karmaşık işleri bile tereyağından kıl çeker gibi halletmenizi sağlıyor. Çevrenizdekiler titizliğinize hayran kalacak.',
                    love: 'İlişkilerde samimiyet ve özen ön planda. Sevginizi sözlerle değil, partnerinizin hayatını kolaylaştıracak küçük inceliklerle göstereceksiniz.',
                    money: 'Hesap kitap, bütçe yönetimi ve harcama kontrolünde harikalar yaratıyorsunuz.',
                    health: 'Sindirim sisteminizi dinlendirin. Probiyotik ve lifli besinler tüketmek iyi gelecektir.'
                },
                dun: {
                    general: 'Dün tamamladığınız temizlik veya dosya düzeni bugün işinizi olağanüstü kolaylaştırdı.',
                    love: 'Dün gösterdiğiniz anlayış partnerinizi çok rahatlattı.',
                    money: 'Gereksiz bir abonelik veya masrafı dün iptal etmeniz kazandırdı.',
                    health: 'Düzenli beslenme alışkanlığınız enerjinizi diri tuttu.'
                },
                yarin: {
                    general: 'Yarın yeni bir uzmanlık veya beceri geliştirme konusunda önemli bir adım atacaksınız.',
                    love: 'Birlikte planlanan bir seyahat veya etkinlik aşkınıza renk katacak.',
                    money: 'İş yerinde verimliliğiniz üst yönetim tarafından ödüllendirilebilir.',
                    health: 'Zihinsel yorgunluğa karşı papatya veya melisa çayı için.'
                },
                haftalik: {
                    general: 'Hafta boyunca iş ortamınızda düzen ve disiplin sağlayacak, verimliliğinizi ikiye katlayacaksınız.',
                    love: 'Küçük detaylara takılmak yerine büyük resimdeki sevgiye odaklanmalısınız.',
                    money: 'Tasarruf hedeflerinize ulaştığınız tatmin edici bir hafta.',
                    health: 'Bağırsak floranızı güçlendiren beslenme programına devam edin.'
                },
                aylik: {
                    general: 'Bu ay kariyerinizde titizliğinizin ve emeğinizin karşılığını fazlasıyla alacaksınız. Yeni bir terfi veya proje kapıda.',
                    love: 'İlişkinizde taşlar yerine oturuyor, huzur hakim oluyor.',
                    money: 'Maddi anlamda istikrarlı bir yükseliş grafiği yakalayacaksınız.',
                    health: 'Bedeninizi düzenli egzersiz ve sağlıklı uykuyla şımartın.'
                }
            },
            'Terazi': {
                symbol: '♎',
                dates: '23 Eylül - 22 Ekim',
                motto: '"Denge, adalet ve estetik benim hayat felsefemdir."',
                planet: 'Venüs',
                element: 'Hava',
                quality: 'Öncü',
                stone: 'Safir / Pembe Kuvars (Cuma)',
                luckyNum: '6 & 24',
                luckyColor: 'Pastel Pembe & Bebek Mavisi',
                bugun: {
                    general: 'Venüs çekiciliğinizi ve zarafetinizi zirveye taşıyor. İkili ilişkilerde, ortaklıklarda ve sosyal çevrede diplomasi yeteneğinizle tüm anlaşmazlıkları barışa dönüştüreceksiniz.',
                    love: 'Romantizm kapınızı çalıyor. Sevdiğinizle paylaştığınız anlar masal gibi geçecek; bekarsanız kalbinizi çarptıracak biriyle tanışabilirsiniz.',
                    money: 'Sanat, tasarım, moda veya ortaklık içeren projelerden kazanç sağlama şansınız yüksek.',
                    health: 'Böbrek sağlığınız için gün boyunca bol su için ve bel bölgenizi sıcak tutun.'
                },
                dun: {
                    general: 'Dün yaşanan bir fikir ayrılığını uzlaşmayla çözmeniz itibarınızı artırdı.',
                    love: 'Dünkü romantik sohbet partnerinizle aranızdaki mesafeleri sıfırladı.',
                    money: 'Ortak bir harcamada dün gösterdiğiniz dengeleyici tutum takdir topladı.',
                    health: 'Hafif yoga veya esneme hareketleri dünün yorgunluğunu aldı.'
                },
                yarin: {
                    general: 'Yarın estetik bir değişim, kuaför veya alışveriş için kusursuz bir gün olacak.',
                    love: 'Partnerinizden gelecek sürpriz bir iltifat gününüzü aydınlatacak.',
                    money: 'Yeni bir sözleşme veya ortaklık teklifini değerlendirebilirsiniz.',
                    health: 'Tuz tüketimini azaltarak vücuttaki ödemi atın.'
                },
                haftalik: {
                    general: 'Hafta boyunca adalet ve denge arayışınız sonuç veriyor. Sosyal davetler ve organizasyonların aranan yüzü olacaksınız.',
                    love: 'Aşk hayatınızda en tatlı ve uyumlu dönemlerden biri yaşanıyor.',
                    money: 'Gelir-gider dengesini mükemmel şekilde kuracaksınız.',
                    health: 'Cilt bakımınıza özen gösterin, doğal maskeler uygulayın.'
                },
                aylik: {
                    general: 'Bu ay Güneş burcunuzdan geçerken hayatınızda yepyeni bir sayfa açılıyor. Şans ve bereket sizinle!',
                    love: 'Evlilik, nişan veya ilişkinin adını koyma dönemi.',
                    money: 'Beklediğiniz bir tazminat, kredi veya ortaklık kazancı elinize geçecek.',
                    health: 'Enerjiniz ve neşeniz en yüksek seviyede olacak.'
                }
            },
            'Akrep': {
                symbol: '♏',
                dates: '23 Ekim - 21 Kasım',
                motto: '"Küllerimden yeniden doğar, gerçeğin peşini asla bırakmam!"',
                planet: 'Plüton & Mars',
                element: 'Su',
                quality: 'Sabit',
                stone: 'Topaz / Obsidyen (Salı)',
                luckyNum: '8 & 13',
                luckyColor: 'Bordo & Gece Siyahı',
                bugun: {
                    general: 'Manyetik auranız ve derin sezgileriniz bugün etrafınızdaki her şeyi bir röntgen gibi görmenizi sağlıyor. Gizli kalmış hiçbir detay gözünüzden kaçmayacak, gücünüzü hissettireceksiniz.',
                    love: 'Aşkta tutku tavan yapıyor. Yüzeysel konuşmalar yerine derin bağlar ve yoğun duygusal paylaşımlar yaşanacak.',
                    money: 'Ortaklaşa kazançlar, yatırımlar veya borçların kapatılması konusunda stratejik adımlar atacaksınız.',
                    health: 'Zihinsel ve bedensel detoks için harika bir gün. Su sporları ve dinlendirici müzikler iyi gelecektir.'
                },
                dun: {
                    general: 'Dün hissettiğiniz bir şüphenin bugün tamamen doğru çıktığına şahit oldunuz.',
                    love: 'Dün partnerinizle yaşadığınız derin konuşma güven tazeledi.',
                    money: 'Finansal bir riski dün ustalıkla bertaraf ettiniz.',
                    health: 'Bedeninizi dinleyerek güne çok daha enerjik uyandınız.'
                },
                yarin: {
                    general: 'Yarın kariyerinizde güç ve otorite kazanacağınız gizli bir fırsat kapınızı çalabilir.',
                    love: 'Tutkulu bakışmalar ve çekim gücü aşkınızı alevlendirecek.',
                    money: 'Yatırımlarınızdan sürpriz bir kar payı elde edebilirsiniz.',
                    health: 'Boşaltım sisteminizi destekleyecek doğal sıvılar tüketin.'
                },
                haftalik: {
                    general: 'Hafta boyunca dönüşüm ve yenilenme enerjisi hakim. Eskimiş bağları ve alışkanlıkları geride bırakıyorsunuz.',
                    love: 'İlişkinizde sadakat ve güven her zamankinden daha kıymetli olacak.',
                    money: 'Banka, kredi veya vergi konularında olumlu haberler alacaksınız.',
                    health: 'Stresi vücutta biriktirmemek için tempolu spor yapın.'
                },
                aylik: {
                    general: 'Bu ay sizin ayınız! Doğum günü döngünüz başlarken hayatınızda büyük bir sıçrama yapacaksınız. Gücünüze inanın.',
                    love: 'Aşk hayatınızda fırtınalı ama bir o kadar da büyüleyici gelişmeler kapıda.',
                    money: 'Maddi açıdan gücünüzü ve itibarınızı ikiye katlayacaksınız.',
                    health: 'Yenilenme enerjisiyle kendinizi gençleşmiş hissedeceksiniz.'
                }
            },
            'Yay': {
                symbol: '♐',
                dates: '22 Kasım - 21 Aralık',
                motto: '"Özgürlük benim nefesimdir, keşfetmek ise yaşam amacım!"',
                planet: 'Jüpiter',
                element: 'Ateş',
                quality: 'Değişken',
                stone: 'Turkuaz / Lapis Lazuli (Perşembe)',
                luckyNum: '3 & 12',
                luckyColor: 'Mor & İndigo Mavisi',
                bugun: {
                    general: 'Jüpiter şans ve iyimserlik kapılarını ardına kadar açıyor. Vizyonunuz genişliyor; yeni seyahatler, yabancılarla iş birlikleri veya yeni felsefi konulara merakınız tavan yapacak.',
                    love: 'İlişkinizde neşe, espri ve özgür ruh hakim. Birlikte yeni yerler keşfetmek aşkınızı besleyecektir.',
                    money: 'Yurt dışı bağlantılı işler, eğitim veya ticaret alanında şanslı fırsatlar doğabilir.',
                    health: 'Uyluk ve kalça kaslarınızı esnetin. Doğa yürüyüşleri ve açık hava aktiviteleri tam size göre.'
                },
                dun: {
                    general: 'Dün planladığınız bir rota veya fikir bugün heyecan verici bir gerçeğe dönüşüyor.',
                    love: 'Dünkü neşeli tavrınız çevrenizdeki herkesin gününü güzelleştirdi.',
                    money: 'Beklenmedik bir fırsat dün karşınıza çıktı, değerlendirmeye aldınız.',
                    health: 'Güne enerjik bir başlangıç yaptınız.'
                },
                yarin: {
                    general: 'Yarın yeni bir eğitime başlamak veya uzun vadeli bir seyahat planı yapmak için mükemmel bir gün.',
                    love: 'Farklı kültürden veya şehirden biriyle heyecan verici bir diyalog başlayabilir.',
                    money: 'Cömertliğiniz takdir toplasa da bütçe sınırlarını aşmamaya dikkat edin.',
                    health: 'Karaciğer sağlığınızı korumak için bol su ve yeşillik tüketin.'
                },
                haftalik: {
                    general: 'Hafta boyunca pozitif enerjinizle girdiğiniz her ortamda neşe saçacaksınız. Şans yanınızda.',
                    love: 'Birlikte eğlenmek ve gülmek ilişkinizi sağlamlaştıracak.',
                    money: 'Yayıncılık, akademi veya e-ticaret projelerinde karlı gelişmeler var.',
                    health: 'Hareketsiz kalmamaya dikkat edin, sporu hayatınıza dahil edin.'
                },
                aylik: {
                    general: 'Bu ay ufkunuza yeni hedefler koyacak ve sınırlarınızı aşacaksınız. Yurt dışı veya yeni projeler gündemde.',
                    love: 'Aşk hayatınızda heyecan verici sürprizler kapınızı çalacak.',
                    money: 'Jüpiter desteğiyle gelirlerinizde artış yaşanacak.',
                    health: 'Moralinizin yüksekliği beden sağlığınızı da yukarı taşıyacak.'
                }
            },
            'Oğlak': {
                symbol: '♑',
                dates: '22 Aralık - 19 Ocak',
                motto: '"Sabır ve disiplinle tırmandığım zirve, bana aittir!"',
                planet: 'Satürn',
                element: 'Toprak',
                quality: 'Öncü',
                stone: 'Granat / Oniks (Cumartesi)',
                luckyNum: '4 & 8',
                luckyColor: 'Kömür Grisi & Orman Yeşili',
                bugun: {
                    general: 'Satürn disiplini ve kararlılığı bugün hedeflerinize kilitlenmenizi sağlıyor. Üst yönetimle görüşmeler, kariyer planlaması ve uzun vadeli stratejilerde rakipsizsiniz.',
                    love: 'İlişkilerde ciddiyet, sadakat ve sorumluluk bilinci ön planda. Sevdiğinize güven vermek ilişkinizin temel taşıdır.',
                    money: 'Geleceğinizi güvenceye alacak yatırımlar ve birikimler konusunda son derece akılcı kararlar alacaksınız.',
                    health: 'Diz, eklem ve kemik sağlığınıza dikkat edin. Kalsiyum zengini besinler ve duruş egzersizleri uygulayın.'
                },
                dun: {
                    general: 'Dün gösterdiğiniz sabır bugün hak ettiğiniz saygıyı ve takdiri getirdi.',
                    love: 'Dün verdiğiniz sözler partnerinizin size olan güvenini perçinledi.',
                    money: 'Tasarruf politikanız dün bütçenize can suyu oldu.',
                    health: 'Düzenli uyku sayesinde güne zinde başladınız.'
                },
                yarin: {
                    general: 'Yarın kariyerinizde önemli bir kilometre taşını geride bırakacaksınız.',
                    love: 'Birlikte gelecek planları yapmak ilişkinize yön verecek.',
                    money: 'Gayrimenkul veya kurumsal bir anlaşma netleşebilir.',
                    health: 'Sırt ve omurga kaslarınızı güçlendirecek esneme hareketleri yapın.'
                },
                haftalik: {
                    general: 'Hafta boyunca iş disiplininiz ve çalışkanlığınızla herkesin gözdesi olacaksınız. Zirveye bir adım daha yaklaştınız.',
                    love: 'Sadakat ve karşılıklı destek aşkınızı taçlandıracak.',
                    money: 'Maddi alanda sağlam adımlar ve uzun vadeli kazanç kapıları aralanıyor.',
                    health: 'Diş ve kemik kontrollerinizi ihmal etmeyin.'
                },
                aylik: {
                    general: 'Bu ay kariyerinizde beklediğiniz o büyük terfi veya unvan değişikliği gerçekleşebilir. Emeklerinizin karşılığı geliyor.',
                    love: 'İlişkinizde kalıcı ve resmi adımlar atılabilir.',
                    money: 'Finansal gücünüzü kurumsal bazda pekiştireceksiniz.',
                    health: 'Eklem sağlığınız için hafif tempolu yürüyüşler yapın.'
                }
            },
            'Kova': {
                symbol: '♒',
                dates: '20 Ocak - 18 Şubat',
                motto: '"Gelecek bugünden başlar; özgünlük benim tek kuralımdır!"',
                planet: 'Uranüs & Satürn',
                element: 'Hava',
                quality: 'Sabit',
                stone: 'Ametist / Turkuaz (Cumartesi)',
                luckyNum: '11 & 22',
                luckyColor: 'Elektrik Mavisi & Metalik Gümüş',
                bugun: {
                    general: 'Uranüs yenilikçi ve sıra dışı fikirlerinizi harekete geçiriyor. Toplumsal projeler, teknoloji, yapay zeka ve ekip çalışmaları için harika bir gün. Fark yaratacaksınız!',
                    love: 'Aşkta özgürlük ve arkadaşlık temeli çok önemli. Partnerinizle hem en iyi dost hem tutkulu bir çift olmayı başaracaksınız.',
                    money: 'Dijital projeler, teknolojik yatırımlar veya yaratıcı işlerden gelir elde etme fırsatı doğabilir.',
                    health: 'Dolaşım sisteminizi ve ayak bileklerinizi koruyun; gün boyu hareketsiz kalmamaya özen gösterin.'
                },
                dun: {
                    general: 'Dün ortaya attığınız vizyoner bir fikir bugün çalışma arkadaşlarınız tarafından benimsendi.',
                    love: 'Dünkü samimi arkadaşça yaklaşım aranızdaki buzları eritti.',
                    money: 'Teknoloji harcamalarında dün yaptığınız araştırma tasarruf sağladı.',
                    health: 'Zihinsel detoks yaparak stresten arındınız.'
                },
                yarin: {
                    general: 'Yarın bir dernek, topluluk veya sosyal grupta öne çıkan bir konuşma yapabilirsiniz.',
                    love: 'Ortak idealleri paylaştığınız biri kalbinizi heyecanlandırabilir.',
                    money: 'Geleceğe dönük projelere fon veya destek bulabilirsiniz.',
                    health: 'Kan dolaşımınızı hızlandırmak için kısa molalarda yürüyüş yapın.'
                },
                haftalik: {
                    general: 'Hafta boyunca yenilikçi projeler ve sosyal ağlar hayatınızın merkezinde olacak. Orijinal fikirleriniz alkış alacak.',
                    love: 'Alışılmışın dışında, heyecan verici bir ilişki dinamiği başlıyor.',
                    money: 'Yenilikçi girişimler ve dijital platformlar kazanç getirecek.',
                    health: 'Varis ve bacak ağrılarına karşı ayaklarınızı dinlendirin.'
                },
                aylik: {
                    general: 'Bu ay hayatınızda devrim niteliğinde kararlar alabilirsiniz. Kalıpları kırıp kendi yolunuzu çizeceksiniz.',
                    love: 'Ruh eşinizle tanışabilir veya var olan ilişkide özgürlük dengesini kurabilirsiniz.',
                    money: 'Beklenmedik bir kaynaktan teknolojik veya fikri gelir akışı sağlanacak.',
                    health: 'Doğal beslenme ve temiz hava zihninizi açacak.'
                }
            },
            'Balık': {
                symbol: '♓',
                dates: '19 Şubat - 20 Mart',
                motto: '"Hayal edebildiğim her şey, gerçeğin büyülü bir yansımasıdır."',
                planet: 'Neptün & Jüpiter',
                element: 'Su',
                quality: 'Değişken',
                stone: 'Akvamarin / Ametist (Perşembe)',
                luckyNum: '7 & 16',
                luckyColor: 'Deniz Yeşili & Lavanta',
                bugun: {
                    general: 'Neptün sanatsal yeteneklerinizi, empati duygunuzu ve rüyalarınızı zenginleştiriyor. Sezgileriniz bugün adeta bir pusula gibi çalışacak; çevrenizdeki insanların ruh halini anında hissedeceksiniz.',
                    love: 'Aşkta masalsı ve romantik esintiler var. Şiirsel bir sevgi dili ve derin duygusal bağlılık partnerinizle aranızdaki bağı güçlendirecek.',
                    money: 'Yaratıcı işler, sanat, danışmanlık veya şifa konularından gelir kapıları açılabilir.',
                    health: 'Ayak sağlığınıza özen gösterin; ılık bir ayak banyosu ve rahatlatıcı masaj tüm günün yorgunluğunu alır.'
                },
                dun: {
                    general: 'Dün gördüğünüz bir rüya veya hissettiğiniz bir sezgi bugün anlam kazandı.',
                    love: 'Dünkü romantik paylaşım ilişkinize sihirli bir dokunuş yaptı.',
                    money: 'Harcamalarda dün gösterdiğiniz temkinli duruş bütçenizi korudu.',
                    health: 'Müzik dinleyerek ruhunuzu dinlendirdiniz.'
                },
                yarin: {
                    general: 'Yarın yaratıcı bir projeye başlamak veya sanatsal bir etkinliğe katılmak için harika bir gün.',
                    love: 'Kalbinizi ısıtacak tatlı bir mesaj veya sürpriz bir arama gelebilir.',
                    money: 'İyilik yaparken sınırlarınızı koruyun, suistimallere izin vermeyin.',
                    health: 'Bağışıklığınızı destekleyecek C vitamini ve taze meyveler tüketin.'
                },
                haftalik: {
                    general: 'Hafta boyunca manevi enerjiniz ve sezgisel gücünüz yüksek olacak. İç sesinize kulak verin.',
                    love: 'Karşılıksız sevgi ve derin bir ruhsal bağ ilişkinizi sarıp sarmalayacak.',
                    money: 'Sanatsal ve yardım projelerinde maddi doyum elde edeceksiniz.',
                    health: 'Lenf sistemini desteklemek için bol su için ve tuzdan uzak durun.'
                },
                aylik: {
                    general: 'Bu ay hayallerinizin somutlaşmaya başladığını göreceksiniz. İlham perileri sizinle!',
                    love: 'Romantizmin doruklarına çıkacağınız, kalbinizi eriten gelişmeler yaşanacak.',
                    money: 'Beklemediğiniz bir kaynaktan mucizevi bir maddi destek gelebilir.',
                    health: 'Ruh-beden-zihin dengesini meditasyon ve doğa yürüyüşleriyle koruyun.'
                }
            }
        };

        // 99 LVL BURÇ SEÇİMİ VE GÜNCELLEME
        function switchAstroSign(signName) {
            currentAstroSign = signName;
            var data = ZODIAC_99LVL_DATA[signName] || ZODIAC_99LVL_DATA['Koç'];
            
            // Başlık & İsim & Sembol
            var nameEl = document.getElementById('astro-modal-name');
            var symEl = document.getElementById('astro-modal-symbol');
            var dateEl = document.getElementById('astro-modal-dates');
            var selectEl = document.getElementById('astro-sign-select');

            if (nameEl) nameEl.innerText = signName;
            if (symEl) symEl.innerText = data.symbol;
            if (dateEl) dateEl.innerText = data.dates;
            if (selectEl && selectEl.value !== signName) selectEl.value = signName;

            // Kimlik Şeridi (Motto, Gezegen, Element, Nitelik, Taş)
            var mottoEl = document.getElementById('astro-motto');
            var planetEl = document.getElementById('astro-planet');
            var elementEl = document.getElementById('astro-element');
            var qualityEl = document.getElementById('astro-quality');
            var stoneEl = document.getElementById('astro-stone');

            if (mottoEl) mottoEl.innerText = data.motto;
            if (planetEl) planetEl.innerText = data.planet;
            if (elementEl) elementEl.innerText = data.element;
            if (qualityEl) qualityEl.innerText = data.quality;
            if (stoneEl) stoneEl.innerText = data.stone;

            // Şanslı Rakam & Renk
            var numEl = document.getElementById('astro-lucky-num');
            var colEl = document.getElementById('astro-lucky-color');
            if (numEl) numEl.innerText = data.luckyNum;
            if (colEl) colEl.innerText = data.luckyColor;

            // Aktif periyot metinlerini güncelle
            renderAstroPeriodContent(currentAstroPeriod);
        }
        window.switchAstroSign = switchAstroSign;

        // 99 LVL ZAMAN SEKMELERİ (Bugün, Dün, Yarın, Haftalık, Aylık, Uyum, Yükselen)
        function switchAstroTab(tabKey) {
            currentAstroPeriod = tabKey;

            // Tüm sekme buton stillerini sıfırla
            var tabs = document.querySelectorAll('.astro-period-tab');
            tabs.forEach(function(t) {
                t.classList.remove('bg-purple-600', 'text-white');
                if (!t.id.includes('uyum') && !t.id.includes('yukselen')) {
                    t.classList.add('bg-slate-800/90', 'text-slate-300');
                }
            });

            var activeTabBtn = document.getElementById('astro-tab-' + tabKey);
            if (activeTabBtn) {
                activeTabBtn.classList.remove('bg-slate-800/90', 'text-slate-300');
                activeTabBtn.classList.add('bg-purple-600', 'text-white');
            }

            // Panelleri yönet
            var viewContent = document.getElementById('astro-view-content');
            var viewCompat = document.getElementById('astro-view-compatibility');
            var viewRising = document.getElementById('astro-view-rising');

            if (tabKey === 'uyum') {
                if (viewContent) viewContent.style.display = 'none';
                if (viewRising) viewRising.style.display = 'none';
                if (viewCompat) {
                    viewCompat.style.display = 'block';
                    var aSel = document.getElementById('compat-sign-a');
                    if (aSel) aSel.value = currentAstroSign;
                    calculateAstroCompatibility();
                }
            } else if (tabKey === 'yukselen') {
                if (viewContent) viewContent.style.display = 'none';
                if (viewCompat) viewCompat.style.display = 'none';
                if (viewRising) {
                    viewRising.style.display = 'block';
                    var sSel = document.getElementById('rising-sun-sign');
                    if (sSel) sSel.value = currentAstroSign;
                    calculateRisingSign();
                }
            } else {
                if (viewCompat) viewCompat.style.display = 'none';
                if (viewRising) viewRising.style.display = 'none';
                if (viewContent) viewContent.style.display = 'block';
                renderAstroPeriodContent(tabKey);
            }
        }
        window.switchAstroTab = switchAstroTab;

        // PERİYOT METİNLERİNİ DOLDURMA
        function renderAstroPeriodContent(periodKey) {
            var data = ZODIAC_99LVL_DATA[currentAstroSign] || ZODIAC_99LVL_DATA['Koç'];
            var pData = data[periodKey] || data['bugun'];

            var dateTitleEl = document.getElementById('astro-period-title');
            var gEl = document.getElementById('astro-text-general');
            var lEl = document.getElementById('astro-text-love');
            var mEl = document.getElementById('astro-text-money');
            var hEl = document.getElementById('astro-text-health');
            var luckyBox = document.getElementById('astro-lucky-box');

            var now = new Date();
            var options = { day: 'numeric', month: 'long', year: 'numeric' };

            if (periodKey === 'bugun') {
                if (dateTitleEl) dateTitleEl.innerHTML = '📅 <strong>' + now.toLocaleDateString('tr-TR', options) + '</strong> Günlük Yorumu';
                if (luckyBox) luckyBox.style.display = 'grid';
            } else if (periodKey === 'dun') {
                var yesterday = new Date(now);
                yesterday.setDate(now.getDate() - 1);
                if (dateTitleEl) dateTitleEl.innerHTML = '⏪ <strong>' + yesterday.toLocaleDateString('tr-TR', options) + '</strong> Dünün Analizi';
                if (luckyBox) luckyBox.style.display = 'none';
            } else if (periodKey === 'yarin') {
                var tomorrow = new Date(now);
                tomorrow.setDate(now.getDate() + 1);
                if (dateTitleEl) dateTitleEl.innerHTML = '⏩ <strong>' + tomorrow.toLocaleDateString('tr-TR', options) + '</strong> Yarının Gökyüzü Rehberi';
                if (luckyBox) luckyBox.style.display = 'none';
            } else if (periodKey === 'haftalik') {
                if (dateTitleEl) dateTitleEl.innerHTML = '📆 <strong>Haftalık Gökyüzü Rehberi</strong> (Bu Hafta)';
                if (luckyBox) luckyBox.style.display = 'none';
            } else if (periodKey === 'aylik') {
                var monthStr = now.toLocaleDateString('tr-TR', { month: 'long', year: 'numeric' });
                if (dateTitleEl) dateTitleEl.innerHTML = '🌙 <strong>' + monthStr + '</strong> Aylık Burç Döngüsü';
                if (luckyBox) luckyBox.style.display = 'none';
            }

            if (gEl) gEl.innerText = pData.general;
            if (lEl) lEl.innerText = pData.love;
            if (mEl) mEl.innerText = pData.money;
            if (hEl) hEl.innerText = pData.health;
        }

        // BURÇ UYUMU HESAPLAYICI (AŞK, İLETİŞİM, TUTKU)
        function calculateAstroCompatibility() {
            var signA = document.getElementById('compat-sign-a') ? document.getElementById('compat-sign-a').value : 'Koç';
            var signB = document.getElementById('compat-sign-b') ? document.getElementById('compat-sign-b').value : 'Terazi';

            var dataA = ZODIAC_99LVL_DATA[signA] || ZODIAC_99LVL_DATA['Koç'];
            var dataB = ZODIAC_99LVL_DATA[signB] || ZODIAC_99LVL_DATA['Terazi'];

            var elA = dataA.element;
            var elB = dataB.element;

            var love = 80;
            var comm = 75;
            var passion = 85;
            var desc = '';

            if (elA === elB) {
                // Aynı element
                love = 92; comm = 88; passion = 90;
                desc = 'Aynı element ailesindensiniz! Birbirinizin hislerini, tepkilerini ve yaşam tarzını kelimeler olmadan bile anlarsınız. Ruh eşi seviyesinde güçlü ve doğal bir uyumunuz var.';
            } else if ((elA === 'Ateş' && elB === 'Hava') || (elA === 'Hava' && elB === 'Ateş')) {
                // Ateş & Hava
                love = 94; comm = 95; passion = 92;
                desc = 'Hava ateşi körükler, ateş havayı ısıtır! İletişiminiz kahkahalar ve derin sohbetlerle doludur. Birlikteyken zamanın nasıl geçtiğini anlamazsınız; son derece heyecan verici ve dinamik bir ilişki.';
            } else if ((elA === 'Toprak' && elB === 'Su') || (elA === 'Su' && elB === 'Toprak')) {
                // Toprak & Su
                love = 96; comm = 86; passion = 89;
                desc = 'Su toprağı besler, bereket ve çiçek açtırır! Karşılıklı güven, sadakat ve şefkat bu birlikteliğin temelidir. Birbirinizi sakinleştirir, evlilik ve uzun vadeli huzur için en ideal eşleşmelerdendir.';
            } else if ((elA === 'Ateş' && elB === 'Su') || (elA === 'Su' && elB === 'Ateş')) {
                // Ateş & Su
                love = 78; comm = 70; passion = 96;
                desc = 'Buharlı, yoğun ve yüksek çekimli bir ilişki! Bir tarafta ateşin coşkusu, diğer tarafta suyun derin duyguları var. Tutku tavan yapar ancak birbirinizin sınırlarına saygı duymak kilit önemdedir.';
            } else if ((elA === 'Toprak' && elB === 'Hava') || (elA === 'Hava' && elB === 'Toprak')) {
                // Toprak & Hava
                love = 72; comm = 82; passion = 70;
                desc = 'Biri pratik ve gerçekçi, diğeri zihinsel ve hayalperest. Birbirinizi dengelemeyi başarırsanız hayatı kusursuz yöneten bir süper ikili olursunuz.';
            } else {
                // Ateş & Toprak vb.
                love = 75; comm = 76; passion = 80;
                desc = 'Farklı karakterler zıt kutuplar gibi birbirini çeker. Sabır ve anlayışla yaklaşıldığında birbirinizin eksik parçalarını tamamlayarak sağlam bir bağ kurarsınız.';
            }

            var total = Math.round((love * 0.4) + (comm * 0.3) + (passion * 0.3));

            var namesEl = document.getElementById('compat-names');
            var totalEl = document.getElementById('compat-total-badge');
            var loveScoreEl = document.getElementById('compat-love-score');
            var loveBarEl = document.getElementById('compat-love-bar');
            var commScoreEl = document.getElementById('compat-comm-score');
            var commBarEl = document.getElementById('compat-comm-bar');
            var passionScoreEl = document.getElementById('compat-passion-score');
            var passionBarEl = document.getElementById('compat-passion-bar');
            var descEl = document.getElementById('compat-desc');

            if (namesEl) namesEl.innerText = signA + ' & ' + signB + ' Uyumu';
            if (totalEl) totalEl.innerText = 'Genel Uyum: %' + total;
            if (loveScoreEl) loveScoreEl.innerText = '%' + love;
            if (loveBarEl) loveBarEl.style.width = love + '%';
            if (commScoreEl) commScoreEl.innerText = '%' + comm;
            if (commBarEl) commBarEl.style.width = comm + '%';
            if (passionScoreEl) passionScoreEl.innerText = '%' + passion;
            if (passionBarEl) passionBarEl.style.width = passion + '%';
            if (descEl) descEl.innerText = desc;
        }
        window.calculateAstroCompatibility = calculateAstroCompatibility;

        // YÜKSELEN BURÇ HESAPLAYICI (ÖZ BURÇ + DOĞUM SAATİ ARALIĞI)
        function calculateRisingSign() {
            var signs = ['Koç', 'Boğa', 'İkizler', 'Yengeç', 'Aslan', 'Başak', 'Terazi', 'Akrep', 'Yay', 'Oğlak', 'Kova', 'Balık'];
            var sunSign = document.getElementById('rising-sun-sign') ? document.getElementById('rising-sun-sign').value : 'Koç';
            var timeOffset = document.getElementById('rising-birth-time') ? parseInt(document.getElementById('rising-birth-time').value, 10) : 0;

            var sunIndex = signs.indexOf(sunSign);
            if (sunIndex === -1) sunIndex = 0;

            var risingIndex = (sunIndex + timeOffset) % 12;
            var risingSignName = signs[risingIndex];
            var risingData = ZODIAC_99LVL_DATA[risingSignName] || ZODIAC_99LVL_DATA['Koç'];

            var symEl = document.getElementById('rising-symbol');
            var nameEl = document.getElementById('rising-name');
            var descEl = document.getElementById('rising-desc');

            if (symEl) symEl.innerText = risingData.symbol;
            if (nameEl) nameEl.innerText = risingSignName + ' Yükselen';

            var risingDescriptions = {
                'Koç': 'Yükselen Koç: Dış dünyaya son derece enerjik, dinamik, doğrudan ve kararlı bir izlenim verirsiniz. Hızlı hareket eder, ilk izlenimde liderlik auranızla dikkat çekersiniz.',
                'Boğa': 'Yükselen Boğa: Sakin, güven veren, estetik ve sağlam bir duruş sergilersiniz. İnsanlar sizin yanınızda huzur bulur; zarif stiliniz ve kaliteli seçimleriniz hemen fark edilir.',
                'İkizler': 'Yükselen İkizler: Hareketli, genç ruhlu, meraklı ve cana yakın bir auranız vardır. Esprili konuşma tarzınızla girdiğiniz her toplulukta hemen kaynaşır, merak uyandırırsınız.',
                'Yengeç': 'Yükselen Yengeç: Şefkatli, koruyucu, içten ve duyarlı bir enerji yayarsınız. İnsanlar size dertlerini anlatmak ister; sıcacık gözleriniz ve nezaketiniz ilk anda kalpleri kazanır.',
                'Aslan': 'Yükselen Aslan: Görkemli saçlar, dik duruş ve adeta ışık saçan bir karizma! Odaya girdiğiniz an tüm bakışları üzerinize çekersiniz; cömert ve asil duruşunuz unutulmazdır.',
                'Başak': 'Yükselen Başak: Temiz, titiz, düzenli ve zeki bir intiba bırakırsınız. Sade şıklığınız ve dikkatli gözlemleriniz çevrenizdekilerde derin bir saygı uyandırır.',
                'Terazi': 'Yükselen Terazi: Büyüleyici bir zarafet, güler yüz ve kusursuz diplomatik üslup. Estetik algınız yüksektir; insanlar sizinle konuşurken kendilerini çok değerli hisseder.',
                'Akrep': 'Yükselen Akrep: Derin, gizemli ve son derece etkileyici bakışlar. İlk anda sır vermeyen ama içeriye çeken çekici bir auranız vardır; çevrenizdekiler gücünüzü anında sezer.',
                'Yay': 'Yükselen Yay: Neşeli, güleç, özgür ve dünyayı kucaklayan geniş bir enerji. Pozitif auranız ve samimi kahkahanız girdiğiniz her yere güneş gibi doğar.',
                'Oğlak': 'Yükselen Oğlak: Ciddi, olgun, güvenilir ve saygın bir duruş. Yaşınızdan daha olgun görünür, profesyonelliğiniz ve ağırbaşlı tavrınızla her ortamda otorite sağlarsınız.',
                'Kova': 'Yükselen Kova: Sıra dışı, özgün, modern ve entelektüel bir aura. Klasik kalıpların dışındaki tarzınız ve bağımsız duruşunuzla anında fark edilirsiniz.',
                'Balık': 'Yükselen Balık: Masalsı, hayalperest, gizemli ve derin duygusal bir çekim gücü. Gözlerinizde derin bir anlam vardır; insanları saran şefkatli ve sanatsal bir havaya sahipsiniz.'
            };

            if (descEl) {
                descEl.innerText = risingDescriptions[risingSignName] || 'Yükselen burcunuz hayata verdiğiniz ilk tepkileri, fiziksel görünüşünüzü ve auranızı yansıtır.';
            }
        }
        window.calculateRisingSign = calculateRisingSign;

        // SOSYAL PAYLAŞIM FONKSİYONLARI (WHATSAPP & LİNK)
        function shareAstroWhatsApp() {
            var text = '✨ ' + currentAstroSign + ' Burcu Günlük Yorumu & Gökyüzü Rehberi: " ' + (ZODIAC_99LVL_DATA[currentAstroSign] ? ZODIAC_99LVL_DATA[currentAstroSign].motto : '') + ' " Gündem Analizi Astroloji Masası\'nda oku: ' + window.location.origin;
            var url = 'https://api.whatsapp.com/send?text=' + encodeURIComponent(text);
            window.open(url, '_blank');
        }
        window.shareAstroWhatsApp = shareAstroWhatsApp;

        function copyAstroLink() {
            var url = window.location.origin + '/#burclar';
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(url).then(function() {
                    alert('✨ ' + currentAstroSign + ' Burcu yorumu bağlantısı panoya kopyalandı!');
                });
            } else {
                prompt('Burç bağlantısını kopyalayın:', url);
            }
        }
        window.copyAstroLink = copyAstroLink;

        // MODAL AÇILIŞ TETİKLEYİCİSİ
        function openAstroModal(name, symbol, dates) {
            var targetSign = name || 'Koç';
            switchAstroSign(targetSign);
            switchAstroTab('bugun');
            openModal('astro-modal');
        }
        window.openAstroModal = openAstroModal;

        // =====================================================================
        // 3. CANLI SÜPER LİG PUAN DURUMU (GENEL / İÇ / DIŞ)
        // =====================================================================
        var STANDINGS_DATA = {
            genel: [
                { rank: 1, team: "🦁 Galatasaray", o: 8, g: 7, b: 1, m: 0, av: "+16", p: 22, lead: true },
                { rank: 2, team: "🟡 Fenerbahçe", o: 8, g: 6, b: 1, m: 1, av: "+14", p: 19 },
                { rank: 3, team: "🔴 Samsunspor", o: 8, g: 6, b: 0, m: 2, av: "+8", p: 18 },
                { rank: 4, team: "🦅 Beşiktaş", o: 8, g: 5, b: 2, m: 1, av: "+7", p: 17 },
                { rank: 5, team: "🌊 Trabzonspor", o: 8, g: 4, b: 3, m: 1, av: "+5", p: 15 },
                { rank: 6, team: "🟣 Eyüpspor", o: 8, g: 3, b: 3, m: 2, av: "+3", p: 12 }
            ],
            icsaha: [
                { rank: 1, team: "🦁 Galatasaray", o: 4, g: 4, b: 0, m: 0, av: "+10", p: 12, lead: true },
                { rank: 2, team: "🟡 Fenerbahçe", o: 4, g: 3, b: 1, m: 0, av: "+8", p: 10 },
                { rank: 3, team: "🦅 Beşiktaş", o: 4, g: 3, b: 1, m: 0, av: "+6", p: 10 },
                { rank: 4, team: "🔴 Samsunspor", o: 4, g: 3, b: 0, m: 1, av: "+4", p: 9 },
                { rank: 5, team: "🌊 Trabzonspor", o: 4, g: 2, b: 2, m: 0, av: "+3", p: 8 },
                { rank: 6, team: "🟣 Eyüpspor", o: 4, g: 2, b: 1, m: 1, av: "+2", p: 7 }
            ],
            deplasman: [
                { rank: 1, team: "🦁 Galatasaray", o: 4, g: 3, b: 1, m: 0, av: "+6", p: 10, lead: true },
                { rank: 2, team: "🔴 Samsunspor", o: 4, g: 3, b: 0, m: 1, av: "+4", p: 9 },
                { rank: 3, team: "🟡 Fenerbahçe", o: 4, g: 3, b: 0, m: 1, av: "+6", p: 9 },
                { rank: 4, team: "🦅 Beşiktaş", o: 4, g: 2, b: 1, m: 1, av: "+1", p: 7 },
                { rank: 5, team: "🌊 Trabzonspor", o: 4, g: 2, b: 1, m: 1, av: "+2", p: 7 },
                { rank: 6, team: "🟣 Eyüpspor", o: 4, g: 1, b: 2, m: 1, av: "+1", p: 5 }
            ]
        };

        function switchStandings(type) {
            var list = STANDINGS_DATA[type] || STANDINGS_DATA.genel;
            var tbody = document.getElementById('standings-table-body');
            var label = document.getElementById('standings-status-label');

            if (label) {
                if (type === 'icsaha') label.innerText = 'İç Saha Sıralaması';
                else if (type === 'deplasman') label.innerText = 'Deplasman Sıralaması';
                else label.innerText = 'Genel Sıralama';
            }

            var tabs = ['genel', 'icsaha', 'deplasman'];
            tabs.forEach(function(t) {
                var btn = document.getElementById('tab-standings-' + t);
                if (btn) {
                    if (t === type) {
                        btn.className = 'flex-1 py-1.5 rounded-lg bg-red-600 text-white font-black text-center transition cursor-pointer shadow-sm';
                    } else {
                        btn.className = 'flex-1 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 text-center transition cursor-pointer';
                    }
                }
            });

            if (!tbody) return;
            tbody.innerHTML = list.map(function(t) {
                return '<tr class="hover:bg-slate-50 transition border-b border-slate-100">' +
                    '<td class="py-1.5 font-bold ' + (t.lead ? 'text-red-600' : 'text-slate-500') + '">' + t.rank + '</td>' +
                    '<td class="py-1.5 font-bold text-slate-900 truncate max-w-[120px]">' + t.team + '</td>' +
                    '<td class="py-1.5 text-center text-slate-600">' + t.o + '</td>' +
                    '<td class="py-1.5 text-center text-slate-600">' + t.g + '</td>' +
                    '<td class="py-1.5 text-center ' + (t.av.startsWith('+') ? 'text-emerald-600 font-semibold' : 'text-slate-600') + '">' + t.av + '</td>' +
                    '<td class="py-1.5 text-right font-black text-slate-900">' + t.p + '</td>' +
                '</tr>';
            }).join('');
        }
        window.switchStandings = switchStandings;

        // =====================================================================
        // 4. HAFTALIK FİKSTÜR & MAÇ PROGRAMI (9, 10, 11. HAFTA GEÇİŞLERİ)
        // =====================================================================
        var FIXTURES_DATA = {
            9: {
                title: "9. Hafta Maçları",
                matches: [
                    { home: "Antalyaspor", away: "Galatasaray", date: "19 Eki • 19:00", badge: "bg-red-500/20 text-red-400 border-red-500/30", highlight: true },
                    { home: "Trabzonspor", away: "Başakşehir", date: "19 Eki • 16:00", badge: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
                    { home: "Fenerbahçe", away: "Samsunspor", date: "20 Eki • 19:00", badge: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30", highlight: true },
                    { home: "Beşiktaş", away: "Konyaspor", date: "20 Eki • 16:00", badge: "bg-slate-500/20 text-slate-300 border-slate-500/30" }
                ]
            },
            10: {
                title: "10. Hafta (Derbi Haftası)",
                matches: [
                    { home: "Galatasaray", away: "Beşiktaş", date: "28 Eki • 20:00", badge: "bg-red-600/30 text-red-300 border-red-500/50", highlight: true },
                    { home: "Fenerbahçe", away: "Bodrum FK", date: "27 Eki • 19:00", badge: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30" },
                    { home: "Göztepe", away: "Trabzonspor", date: "26 Eki • 19:00", badge: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
                    { home: "Kasımpaşa", away: "Samsunspor", date: "26 Eki • 16:00", badge: "bg-slate-500/20 text-slate-300 border-slate-500/30" }
                ]
            },
            11: {
                title: "11. Hafta (Süper Lig)",
                matches: [
                    { home: "Trabzonspor", away: "Fenerbahçe", date: "3 Kas • 19:00", badge: "bg-amber-500/30 text-amber-300 border-amber-500/50", highlight: true },
                    { home: "Beşiktaş", away: "Kasımpaşa", date: "2 Kas • 19:00", badge: "bg-slate-500/20 text-slate-300 border-slate-500/30" },
                    { home: "Samsunspor", away: "Antalyaspor", date: "4 Kas • 20:00", badge: "bg-red-500/20 text-red-400 border-red-500/30" },
                    { home: "Galatasaray", away: "BAY (Maçı Yok)", date: "Haftalık Dinlenme", badge: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" }
                ]
            }
        };

        var currentFixtureWeek = 9;

        function renderFixtures(week) {
            currentFixtureWeek = week;
            var data = FIXTURES_DATA[week] || FIXTURES_DATA[9];
            var titleEl = document.getElementById('fixture-week-badge');
            var listEl = document.getElementById('fixture-matches-list') || document.getElementById('fixtures-matches-list');

            if (titleEl) titleEl.innerText = week + '. Hafta';

            [9, 10, 11].forEach(function(w) {
                var btn = document.getElementById('tab-week-' + w);
                if (btn) {
                    if (w === week) {
                        btn.className = 'flex-1 py-1 rounded-lg bg-red-600 text-white font-black text-center transition cursor-pointer shadow-xs text-xs';
                    } else {
                        btn.className = 'flex-1 py-1 rounded-lg text-slate-600 hover:text-slate-900 text-center transition cursor-pointer text-xs';
                    }
                }
            });

            if (!listEl) return;
            listEl.innerHTML = data.matches.map(function(m) {
                var isHigh = m.highlight;
                var boxCls = isHigh ? 'bg-red-50/50 border-red-200 hover:border-red-400' : 'bg-slate-50 border-slate-200 hover:border-slate-300';
                var textCls = isHigh ? 'text-red-700 font-extrabold' : 'text-slate-900 font-bold';
                var badgeCls = isHigh ? 'bg-red-100 text-red-700 border-red-200' : 'bg-slate-200 text-slate-800 border-slate-300';
                return '<div class="p-2.5 rounded-xl border ' + boxCls + ' flex items-center justify-between transition hover:bg-white shadow-xs">' +
                    '<span class="text-xs sm:text-sm ' + textCls + '">' + m.home + ' - ' + m.away + '</span>' +
                    '<span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded border ' + badgeCls + '">' + m.date + '</span>' +
                '</div>';
            }).join('');
        }
                // Canlı TFF Süper Lig Verisi Çekici
        function fetchLiveSuperlig() {
            fetch('/api/superlig')
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (data && data.success) {
                        if (data.standings && data.standings.length > 0) {
                            STANDINGS_DATA.genel = data.standings;
                            switchStandings('genel');
                        }
                        if (data.matches && data.matches.length > 0) {
                            var w = data.week || 10;
                            currentFixtureWeek = w;
                            FIXTURES_DATA[w] = {
                                title: w + '. Hafta Maçları (Canlı TFF)',
                                matches: data.matches.map(function(m) {
                                    var dtStr = (m.date || '') + (m.time ? ' • ' + m.time : '');
                                    return {
                                        home: m.home,
                                        away: m.away,
                                        date: dtStr || 'Gelecek Maç',
                                        badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
                                        highlight: (m.home.includes('Galatasaray') || m.home.includes('Fenerbahçe') || m.home.includes('Beşiktaş') || m.home.includes('Trabzon') ||
                                                    m.away.includes('Galatasaray') || m.away.includes('Fenerbahçe') || m.away.includes('Beşiktaş') || m.away.includes('Trabzon'))
                                    };
                                })
                            };
                            renderFixtures(w);
                        }
                    }
                })
                .catch(function(err) {
                    console.error('Superlig fetch err:', err);
                });
        }
        window.fetchLiveSuperlig = fetchLiveSuperlig;

        window.renderFixtures = renderFixtures;
        window.setFixtureWeek = function(w) { renderFixtures(w); };
        window.changeFixtureWeek = function(delta) {
            var next = currentFixtureWeek + delta;
            if (next < 9) next = 11;
            if (next > 11) next = 9;
            renderFixtures(next);
        };

        // =====================================================================
        // 5. 81 İL CANLI NAMAZ VAKTİ MOTORU & DİYANET HESAPLAMASI
        // =====================================================================
        var CITY_OFFSETS = {
            "Adana": -19, "Adıyaman": -27, "Afyonkarahisar": -5, "Ağrı": -45, "Amasya": -18,
            "Ankara": -14, "Antalya": -6, "Artvin": -37, "Aydın": 6, "Balıkesir": 4,
            "Bilecik": -1, "Bingöl": -35, "Bitlis": -42, "Bolu": -8, "Burdur": -5,
            "Bursa": 1, "Çanakkale": 9, "Çankırı": -14, "Çorum": -18, "Denizli": 3,
            "Diyarbakır": -34, "Edirne": 6, "Elazığ": -31, "Erzincan": -33, "Erzurum": -39,
            "Eskişehir": -4, "Gaziantep": -25, "Giresun": -26, "Gümüşhane": -30, "Hakkari": -46,
            "Hatay": -21, "Isparta": -5, "Mersin": -17, "İstanbul": 0, "İzmir": 6,
            "Kars": -44, "Kastamonu": -13, "Kayseri": -17, "Kırklareli": 5, "Kırşehir": -15,
            "Kocaeli": -3, "Konya": -13, "Kütahya": -1, "Malatya": -28, "Manisa": 6,
            "Kahramanmaraş": -22, "Mardin": -34, "Muğla": 5, "Muş": -39, "Nevşehir": -16,
            "Niğde": -16, "Ordu": -24, "Rize": -31, "Sakarya": -5, "Samsun": -16,
            "Siirt": -39, "Sinop": -14, "Sivas": -25, "Tekirdağ": 4, "Tokat": -21,
            "Trabzon": -28, "Tunceli": -32, "Şanlıurfa": -29, "Uşak": 2, "Van": -48,
            "Yozgat": -17, "Zonguldak": -7, "Aksaray": -15, "Bayburt": -32, "Karaman": -14,
            "Kırıkkale": -14, "Batman": -36, "Şırnak": -41, "Bartın": -7, "Ardahan": -42,
            "Iğdır": -49, "Yalova": 1, "Karabük": -9, "Kilis": -24, "Osmaniye": -20, "Düzce": -7
        };

        var BASE_TIMES = {
            imsak: 346,  // 05:46
            gunes: 431,  // 07:11
            ogle: 774,   // 12:54
            ikindi: 953, // 15:53
            aksam: 1105, // 18:25
            yatsi: 1184  // 19:44
        };

        function formatMins(m) {
            var h = Math.floor(m / 60) % 24;
            var min = Math.floor(m % 60);
            return (h < 10 ? '0' : '') + h + ':' + (min < 10 ? '0' : '') + min;
        }

        function calculateTimesForCity(cityName) {
            var offset = CITY_OFFSETS[cityName] !== undefined ? CITY_OFFSETS[cityName] : 0;
            return {
                imsak: BASE_TIMES.imsak + offset,
                gunes: BASE_TIMES.gunes + offset,
                ogle: BASE_TIMES.ogle + offset,
                ikindi: BASE_TIMES.ikindi + offset,
                aksam: BASE_TIMES.aksam + offset,
                yatsi: BASE_TIMES.yatsi + offset
            };
        }

        function populateNamazCities() {
            var sel = document.getElementById('namaz-city-select');
            if (!sel || sel.options.length > 0) return;
            var cities = Object.keys(CITY_OFFSETS).sort(function(a, b) {
                return a.localeCompare('tr', { sensitivity: 'base' });
            });
            cities.forEach(function(c) {
                var opt = document.createElement('option');
                opt.value = c;
                opt.innerText = c;
                if (c === 'İstanbul') opt.selected = true;
                sel.appendChild(opt);
            });
        }

        function updateNamazModal(cityName) {
            var times = calculateTimesForCity(cityName);
            var titleEl = document.getElementById('namaz-modal-city-title');
            var cardCity = document.getElementById('card-city-name');
            if (titleEl) titleEl.innerText = cityName;
            if (cardCity) cardCity.innerText = cityName;

            ['imsak', 'gunes', 'ogle', 'ikindi', 'aksam', 'yatsi'].forEach(function(k) {
                var el = document.getElementById('time-' + k);
                if (el) el.innerText = formatMins(times[k]);
            });

            var liveCard = document.getElementById('live-namaz-vakti');
            if (liveCard) {
                liveCard.innerText = 'Yatsı ' + formatMins(times.yatsi);
            }
        }

        function onNamazCityChange(cityName) {
            updateNamazModal(cityName);
        }
        window.onNamazCityChange = onNamazCityChange;

        // Geri Sayım Sayacı (Sıradaki Vakte Kalan Süre)
        function startPrayerCountdown() {
            function tick() {
                var now = new Date();
                var curMins = now.getHours() * 60 + now.getMinutes();
                var curSecs = now.getSeconds();

                var prayers = [
                    { name: "İmsak", time: BASE_TIMES.imsak },
                    { name: "Güneş", time: BASE_TIMES.gunes },
                    { name: "Öğle", time: BASE_TIMES.ogle },
                    { name: "İkindi", time: BASE_TIMES.ikindi },
                    { name: "Akşam (İftar)", time: BASE_TIMES.aksam },
                    { name: "Yatsı", time: BASE_TIMES.yatsi }
                ];

                var next = prayers.find(function(p) { return p.time > curMins; });
                if (!next) next = prayers[0];

                var diffMins = next.time - curMins;
                if (diffMins < 0) diffMins += 24 * 60;
                var diffSecs = 60 - curSecs;
                if (diffSecs === 60) diffSecs = 0;
                else diffMins -= 1;

                var h = Math.floor(diffMins / 60);
                var m = diffMins % 60;
                var s = diffSecs;

                var pad = function(n) { return (n < 10 ? '0' : '') + n; };
                var countdownEl = document.getElementById('next-prayer-countdown');
                var nextNameEl = document.getElementById('next-prayer-name');
                if (countdownEl) countdownEl.innerText = pad(h) + ':' + pad(m) + ':' + pad(s);
                if (nextNameEl) nextNameEl.innerText = next.name;
            }
            setInterval(tick, 1000);
            tick();
        }

        // =====================================================================
        // 6. NÖBETÇİ ECZANELER CANLI VERİ & FİLTRE MOTORU
        // =====================================================================
        var SAMPLE_PHARMACIES = [
            { name: "Merkez Şifa Eczanesi", city: "İstanbul", district: "Kadıköy", address: "Moda Cad. No:42/A", phone: "0216 330 12 34" },
            { name: "Güneş Eczanesi", city: "İstanbul", district: "Şişli", address: "Halaskargazi Cad. No:88", phone: "0212 240 55 66" }
        ];
        var CURRENT_NOBETCI_DATA = [];

        function populateNobetciCities() {
            var sel = document.getElementById('nobetci-city-select');
            if (!sel || sel.options.length > 0) return;
            var cities = Object.keys(CITY_OFFSETS || {}).sort(function(a, b) {
                return a.localeCompare('tr', { sensitivity: 'base' });
            });
            cities.forEach(function(c) {
                var opt = document.createElement('option');
                opt.value = c;
                opt.innerText = c;
                if (c === 'İstanbul') opt.selected = true;
                sel.appendChild(opt);
            });
        }
        window.populateNobetciCities = populateNobetciCities;

        function loadNobetciCity(cityName) {
            var listEl = document.getElementById('nobetci-list');
            var titleEl = document.getElementById('nobetci-city-title');
            var badgeEl = document.getElementById('nobetci-badge');
            if (titleEl) titleEl.innerText = cityName + ' Nöbetçi Eczaneleri';
            if (badgeEl) badgeEl.innerText = '⏳ Yükleniyor...';

            if (listEl) {
                listEl.innerHTML = '<div class="p-6 text-center text-emerald-400 text-xs flex items-center justify-center gap-2">' +
                    '<svg class="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>' +
                    '<span>' + cityName + ' nöbetçi eczaneleri alınıyor...</span></div>';
            }

            fetch('/api/nobetci-eczaneler?city=' + encodeURIComponent(cityName))
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (data && data.pharmacies && data.pharmacies.length > 0) {
                        CURRENT_NOBETCI_DATA = data.pharmacies.map(function(p) {
                            return {
                                name: p.name || 'Eczane',
                                city: cityName,
                                district: p.district || cityName,
                                address: p.address || 'Adres bilgisi mevcut',
                                phone: p.phone || '-',
                                hours: p.hours,
                                status: p.status,
                                is_now_open: p.is_now_open
                            };
                        });
                        if (badgeEl) badgeEl.innerText = '🟢 Canlı (' + CURRENT_NOBETCI_DATA.length + ' Eczane)';
                        renderNobetciList(CURRENT_NOBETCI_DATA);
                    } else {
                        if (badgeEl) badgeEl.innerText = 'Nöbetçi Bilgisi';
                        CURRENT_NOBETCI_DATA = [];
                        if (listEl) {
                            listEl.innerHTML = '<div class="p-6 text-center text-slate-400 text-xs">' + cityName + ' için nöbetçi eczane kaydı bulunamadı. Lütfen birazdan tekrar deneyiniz.</div>';
                        }
                    }
                })
                .catch(function(err) {
                    console.error('Nobetci fetch err:', err);
                    if (badgeEl) badgeEl.innerText = 'Bağlantı Hatası';
                    if (listEl) {
                        listEl.innerHTML = '<div class="p-6 text-center text-slate-400 text-xs">Eczane verisi yüklenirken hata oluştu. Lütfen sayfayı yenileyiniz.</div>';
                    }
                });
        }
        window.loadNobetciCity = loadNobetciCity;

                function renderNobetciList(items) {
            var listEl = document.getElementById('nobetci-list');
            if (!listEl) return;
            if (!items || items.length === 0) {
                listEl.innerHTML = '<div class="p-4 text-center text-slate-400 text-xs">Bu şehir için nöbetçi eczane listelenemedi. Lütfen tekrar deneyin.</div>';
                return;
            }
            listEl.innerHTML = items.map(function(p) {
                var phoneClean = (p.phone || '').replace(/[^0-9+]/g, '');
                var isNowOpen = p.is_now_open;
                var badgeText = p.hours || "18:30 - 08:30 (Sabaha Kadar Açık)";
                var statusText = p.status || (isNowOpen ? "🟢 ŞU AN AÇIK" : "Akşam Nöbetçisi (18:30)");
                var badgeClass = isNowOpen ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" : "bg-blue-500/20 text-blue-300 border-blue-500/40";

                return '<div class="p-3 rounded-xl bg-slate-50 border border-slate-200 hover:border-emerald-500 hover:bg-white transition flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">' +
                    '<div class="min-w-0 flex-1 space-y-1">' +
                        '<div class="flex items-center gap-2 flex-wrap">' +
                            '<span class="font-extrabold text-slate-900 text-xs">' + p.name + '</span>' +
                            '<span class="text-[10px] px-2 py-0.5 rounded font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">' + (p.district || p.city) + '</span>' +
                            '<span class="text-[10px] px-2 py-0.5 rounded font-semibold border ' + badgeClass + '">' + statusText + '</span>' +
                        '</div>' +
                        '<div class="text-[11px] text-slate-300 leading-snug">' + (p.address || '') + '</div>' +
                        '<div class="text-[10px] text-amber-400/90 font-medium flex items-center gap-1">🕒 Nöbet Saatleri: ' + badgeText + '</div>' +
                    '</div>' +
                    '<div class="shrink-0 flex items-center gap-2">' +
                        (phoneClean ? '<a href="tel:' + phoneClean + '" class="w-full sm:w-auto text-center px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center justify-center gap-1 transition shadow cursor-pointer">' +
                            '📞 ' + (p.phone || 'Hemen Ara') +
                        '</a>' : '') +
                    '</div>' +
                '</div>';
            }).join('');
        }

        function filterNobetci(query) {
            var q = (query || '').toLowerCase().trim();
            var source = (CURRENT_NOBETCI_DATA && CURRENT_NOBETCI_DATA.length > 0) ? CURRENT_NOBETCI_DATA : SAMPLE_PHARMACIES;
            if (!q) {
                renderNobetciList(source);
                return;
            }
            var filtered = source.filter(function(p) {
                return (p.name || '').toLowerCase().includes(q) || 
                       (p.city || '').toLowerCase().includes(q) || 
                       (p.district || '').toLowerCase().includes(q) ||
                       (p.address || '').toLowerCase().includes(q);
            });
            renderNobetciList(filtered);
        }
        window.filterNobetci = filterNobetci;

        // =====================================================================
        // 7. KANDİLLİ & AFAD CANLI SON DEPREMLER MOTORU (50 CANLI SARSINTI)
        // =====================================================================
        var LIVE_DEPREM_DATA = [];
        var currentDepremFilter = 'all';
        var isFetchingDeprem = false;

        var SAMPLE_QUAKES = [
            { place: "Ege Denizi - [Çanakkale Ayvacık açıkları]", mag: 4.2, depth: "7.4 km", time: "18:42", provider: "Kandilli", level: "high" },
            { place: "Malatya - Yeşilyurt", mag: 3.4, depth: "10.2 km", time: "16:15", provider: "AFAD", level: "med" },
            { place: "Kahramanmaraş - Göksun", mag: 2.8, depth: "6.8 km", time: "14:20", provider: "AFAD", level: "low" },
            { place: "Akdeniz - Girit Adası Açıkları", mag: 4.5, depth: "14.1 km", time: "11:05", provider: "Kandilli", level: "high" },
            { place: "Marmara Denizi - Yalova Açıkları", mag: 2.3, depth: "9.5 km", time: "09:30", provider: "AFAD", level: "low" }
        ];

        function fetchLiveDeprem(force) {
            if (isFetchingDeprem && !force) return;
            isFetchingDeprem = true;
            var refreshIcon = document.getElementById('deprem-refresh-icon');
            if (refreshIcon) refreshIcon.classList.add('animate-spin');

            fetch('/api/deprem?limit=50')
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (data && data.quakes && data.quakes.length > 0) {
                        LIVE_DEPREM_DATA = data.quakes;
                        var upEl = document.getElementById('deprem-updated-at');
                        if (upEl && data.updated_at) upEl.innerText = 'Son: ' + data.updated_at;
                        applyDepremFilters();
                    } else if (LIVE_DEPREM_DATA.length === 0) {
                        renderDepremList(SAMPLE_QUAKES);
                    }
                })
                .catch(function(err) {
                    console.log('Deprem fetch hatası:', err);
                    if (LIVE_DEPREM_DATA.length === 0) {
                        renderDepremList(SAMPLE_QUAKES);
                    }
                })
                .finally(function() {
                    isFetchingDeprem = false;
                    if (refreshIcon) refreshIcon.classList.remove('animate-spin');
                });
        }
        window.fetchLiveDeprem = fetchLiveDeprem;

        function renderDepremList(items) {
            var listEl = document.getElementById('deprem-list');
            var countEl = document.getElementById('deprem-status-count');
            if (!listEl) return;

            if (countEl) {
                countEl.innerText = items.length + ' sarsıntı listeleniyor';
            }

            if (!items || items.length === 0) {
                listEl.innerHTML = '<div class="p-6 text-center text-slate-500 text-xs">Aradığınız kriterde deprem kaydı bulunamadı.</div>';
                return;
            }

            listEl.innerHTML = items.map(function(q) {
                var badgeClass = 'bg-emerald-50 text-emerald-800 border-emerald-300 font-bold';
                var pingHtml = '';
                if (q.mag >= 4.0) {
                    badgeClass = 'bg-red-50 text-red-800 border-red-300 font-black shadow-xs';
                    pingHtml = '<span class="inline-block w-2 h-2 rounded-full bg-red-600 animate-ping mr-1"></span>';
                } else if (q.mag >= 3.0) {
                    badgeClass = 'bg-amber-50 text-amber-800 border-amber-300 font-bold';
                }

                var provBadge = q.provider ? '<span class="text-[9px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold border border-slate-300">' + q.provider + '</span>' : '';
                var dateInfo = q.date ? '<span class="text-[10px] text-slate-500 mr-1">' + q.date + '</span>' : '';

                return '<div class="p-3 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-between hover:border-red-400 hover:bg-white transition group shadow-xs">' +
                    '<div class="flex items-center gap-3">' +
                        '<div class="flex flex-col items-center justify-center w-12 h-12 rounded-xl border ' + badgeClass + ' shrink-0">' +
                            '<span class="text-base font-black leading-none">' + q.mag.toFixed(1) + '</span>' +
                            '<span class="text-[8px] uppercase tracking-wider opacity-80 mt-0.5">ML</span>' +
                        '</div>' +
                        '<div>' +
                            '<div class="font-bold text-slate-900 text-xs sm:text-sm group-hover:text-red-600 transition">' + pingHtml + q.place + '</div>' +
                            '<div class="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5">' +
                                '<span>Derinlik: <strong class="text-slate-700">' + q.depth + '</strong></span>' +
                                provBadge +
                            '</div>' +
                        '</div>' +
                    '</div>' +
                    '<div class="text-right shrink-0">' +
                        '<div class="text-xs font-black text-slate-800 bg-slate-200/80 px-2 py-0.5 rounded">' + q.time + '</div>' +
                        dateInfo +
                    '</div>' +
                '</div>';
            }).join('');
        }

        function filterDepremMag(level) {
            currentDepremFilter = level;
            var buttons = document.querySelectorAll('.deprem-filter-btn');
            buttons.forEach(function(b) {
                b.classList.remove('bg-rose-600', 'text-white');
                b.classList.add('bg-slate-800/90', 'text-slate-300');
            });
            var activeBtn = document.getElementById('deprem-filter-' + level);
            if (activeBtn) {
                activeBtn.classList.remove('bg-slate-800/90', 'text-slate-300');
                activeBtn.classList.add('bg-rose-600', 'text-white');
            }
            applyDepremFilters();
        }
        window.filterDepremMag = filterDepremMag;

        function searchDeprem(query) {
            applyDepremFilters();
        }
        window.searchDeprem = searchDeprem;

        function applyDepremFilters() {
            var pool = LIVE_DEPREM_DATA.length > 0 ? LIVE_DEPREM_DATA : SAMPLE_QUAKES;
            var searchInput = document.getElementById('deprem-search');
            var q = searchInput ? (searchInput.value || '').toLowerCase().trim() : '';

            var filtered = pool.filter(function(item) {
                if (currentDepremFilter === 'low' && item.mag >= 3.0) return false;
                if (currentDepremFilter === 'med' && (item.mag < 3.0 || item.mag >= 4.0)) return false;
                if (currentDepremFilter === 'high' && item.mag < 4.0) return false;

                if (q) {
                    var matchPlace = item.place.toLowerCase().includes(q);
                    var matchMag = item.mag.toString().includes(q);
                    var matchProv = (item.provider || '').toLowerCase().includes(q);
                    return matchPlace || matchMag || matchProv;
                }
                return true;
            });

            renderDepremList(filtered);
        }

        // openDepremModal üstte lazy tanımlandı
        window.openDepremModal = openDepremModal;
        function closeDepremModal() { closeModal('deprem-modal'); }
        window.closeDepremModal = closeDepremModal;
        // =====================================================================
        // 8. SAYFA YÜKLENDİĞİNDE TÜM SİSTEMLERİ BAŞLAT
        // =====================================================================
        // =====================================================================
        // 🔍 CANLI HABER ARAMA MOTORU (LIVE SEARCH ENGINE)
        // =====================================================================
        var searchDebounceTimer = null;

        function openSearchModal() {
            openModal('search-modal');
            setTimeout(function() {
                var inp = document.getElementById('live-search-input');
                if (inp) inp.focus();
            }, 100);
        }
        window.openSearchModal = openSearchModal;

        function closeSearchModal() {
            closeModal('search-modal');
        }
        window.closeSearchModal = closeSearchModal;

        function clearLiveSearch() {
            var inp = document.getElementById('live-search-input');
            if (inp) {
                inp.value = '';
                inp.focus();
                handleLiveSearch('');
            }
        }
        window.clearLiveSearch = clearLiveSearch;

        function quickSearchTag(tag) {
            var inp = document.getElementById('live-search-input');
            if (inp) {
                inp.value = tag;
                handleLiveSearch(tag);
            }
        }
        window.quickSearchTag = quickSearchTag;

        function handleLiveSearch(query) {
            clearTimeout(searchDebounceTimer);
            var q = (query || '').trim();
            var clearBtn = document.getElementById('live-search-clear-btn');
            var resultsEl = document.getElementById('live-search-results');
            var footerEl = document.getElementById('live-search-footer');
            var countEl = document.getElementById('live-search-count-text');

            if (clearBtn) clearBtn.style.display = q ? 'block' : 'none';

            if (!q || q.length < 2) {
                if (resultsEl) {
                    resultsEl.innerHTML = '<div class="p-6 text-center text-slate-400 text-xs">Aramak istediğiniz konuyu yukarıya yazın veya popüler etiketlere tıklayın.</div>';
                }
                if (footerEl) footerEl.style.display = 'none';
                return;
            }

            if (resultsEl) {
                resultsEl.innerHTML = '<div class="p-6 text-center text-slate-400 text-xs flex items-center justify-center gap-2"><span class="animate-spin text-lg">⏳</span> Aranıyor: "' + q + '"...</div>';
            }

            searchDebounceTimer = setTimeout(function() {
                fetch('/api/search?q=' + encodeURIComponent(q) + '&limit=6')
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (!resultsEl) return;
                        if (!data || !data.results || data.results.length === 0) {
                            resultsEl.innerHTML = '<div class="p-6 text-center text-slate-400 text-xs">"' + q + '" ile eşleşen haber bulunamadı.<br><span class="text-slate-500 text-[11px] mt-1 block">Farklı bir arama terimi deneyebilirsiniz.</span></div>';
                            if (footerEl) footerEl.style.display = 'none';
                            return;
                        }

                        resultsEl.innerHTML = data.results.map(function(item) {
                            return '<a href="/haber/' + item.slug + '" class="p-2.5 rounded-2xl bg-slate-900 border border-slate-800 hover:border-red-500/50 transition flex items-center gap-3 group block">' +
                                '<img src="' + item.image + '" alt="' + item.title + '" class="w-14 h-12 rounded-xl object-cover shrink-0 border border-slate-700 group-hover:scale-105 transition">' +
                                '<div class="flex-1 min-w-0">' +
                                    '<div class="flex items-center gap-2 mb-0.5">' +
                                        '<span class="text-[9px] font-black uppercase px-2 py-0.5 rounded bg-red-600/20 text-red-400 border border-red-500/30">' + item.category + '</span>' +
                                        '<span class="text-[10px] text-slate-500">' + item.date + '</span>' +
                                    '</div>' +
                                    '<h4 class="text-xs font-bold text-white group-hover:text-red-400 transition truncate">' + item.title + '</h4>' +
                                '</div>' +
                            '</a>';
                        }).join('');

                        if (footerEl && countEl) {
                            footerEl.style.display = 'flex';
                            countEl.innerText = '"' + q + '" ile ilgili sonuçlar';
                        }
                    })
                    .catch(function(err) {
                        if (resultsEl) resultsEl.innerHTML = '<div class="p-4 text-center text-rose-400 text-xs">Arama sırasında bir hata oluştu.</div>';
                    });
            }, 250);
        }
        window.handleLiveSearch = handleLiveSearch;

        function handleSearchSubmit(e) {
            var inp = document.getElementById('live-search-input');
            if (!inp || !inp.value.trim()) {
                e.preventDefault();
                return false;
            }
            return true;
        }
        window.handleSearchSubmit = handleSearchSubmit;

        function submitFullSearch() {
            var inp = document.getElementById('live-search-input');
            if (inp && inp.value.trim()) {
                window.location.href = '/?q=' + encodeURIComponent(inp.value.trim());
            }
        }
        window.submitFullSearch = submitFullSearch;

        // Klavye Kısayolu: Ctrl + K veya Cmd + K
        document.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                openSearchModal();
            }
        });

        function initApp() {
            if (window.lucide) window.lucide.createIcons();

            var btnNamaz = document.getElementById('btn-open-namaz');
            if (btnNamaz) btnNamaz.addEventListener('click', openNamazModal);

            var btnNobetci = document.getElementById('btn-open-nobetci');
            if (btnNobetci) btnNobetci.addEventListener('click', openNobetciModal);

            var btnDeprem = document.getElementById('btn-open-deprem');
            if (btnDeprem) btnDeprem.addEventListener('click', openDepremModal);
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initApp);
        } else {
            initApp();
        }

