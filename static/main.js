document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        const loginBtn = document.getElementById('loginBtn');
        
        loginForm.addEventListener('submit', function() {
            const btnText = loginBtn.innerHTML;
            loginBtn.disabled = true;
            loginBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Giriş Yapılıyor...';
            
            setTimeout(function() {
                loginForm.submit();
            }, 100);
        });
    }
    
    const keywordsContentTextarea = document.getElementById('content');
    const keywordsEditBtn = document.getElementById('editKeywordsBtn');
    const keywordsCancelBtn = document.getElementById('cancelEditBtn');
    const keywordsValidateBtn = document.getElementById('validateBtn');
    const keywordsSaveBtn = document.getElementById('saveBtn');
    
    if (keywordsContentTextarea && keywordsEditBtn && document.getElementById('keywordsForm')) {
        const keywordsViewDiv = document.getElementById('keywordsView');
        const keywordsEditDiv = document.getElementById('keywordsEdit');
        const originalContent = keywordsContentTextarea.value;
        
        function cleanKeywordsTextareaContent() {
            const lines = keywordsContentTextarea.value.split('\n');
            const cleanedLines = [];
            
            let previousLineType = null;
            
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i].trim();
                
                let currentLineType;
                if (line === '') {
                    currentLineType = 'empty';
                } else if (line.startsWith('##')) {
                    currentLineType = 'category';
                } else if (line.startsWith('#')) {
                    currentLineType = 'comment';
                } else {
                    currentLineType = 'keyword';
                }
                
                if (currentLineType === 'empty') {
                    continue;
                }
                
                if (currentLineType === 'category' && previousLineType !== null && previousLineType !== 'empty' && cleanedLines.length > 0) {
                    cleanedLines.push('');
                }
                
                cleanedLines.push(line);
                previousLineType = currentLineType;
            }
            
            keywordsContentTextarea.value = cleanedLines.join('\n');
        }
        
        const keywordsForm = document.getElementById('keywordsForm');
        if (keywordsForm) {
            keywordsForm.addEventListener('submit', function(e) {
                e.preventDefault();
                cleanKeywordsTextareaContent();
                this.submit();
            });
        }
        
        if (keywordsEditBtn) {
            keywordsEditBtn.addEventListener('click', function() {
                keywordsViewDiv.style.display = 'none';
                keywordsEditDiv.style.display = 'block';
                keywordsContentTextarea.focus();
                
                window.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                });
            });
        }
        
        if (keywordsCancelBtn) {
            keywordsCancelBtn.addEventListener('click', function() {
                if (keywordsContentTextarea.value !== originalContent) {
                    if (confirm('Değişiklikleriniz kaydedilmeyecek. Devam etmek istiyor musunuz?')) {
                        keywordsContentTextarea.value = originalContent;
                        keywordsEditDiv.style.display = 'none';
                        keywordsViewDiv.style.display = 'block';
                    }
                } else {
                    keywordsEditDiv.style.display = 'none';
                    keywordsViewDiv.style.display = 'block';
                }
            });
        }
        
        if (keywordsValidateBtn) {
            keywordsValidateBtn.addEventListener('click', function() {
                cleanKeywordsTextareaContent();
                
                const content = keywordsContentTextarea.value.trim();
                let isValid = true;
                let validationMessages = [];
                let currentCategory = 'GENEL';
                
                const lines = content.split('\n');
                
                lines.forEach((line, index) => {
                    line = line.trim();
                    
                    if (line === '' || (line.startsWith('#') && !line.startsWith('##'))) {
                        return;
                    }
                    
                    if (line.startsWith('##')) {
                        const category = line.substring(2).trim();
                        if (!category) {
                            isValid = false;
                            validationMessages.push(`Satır ${index + 1}: Kategori adı boş olamaz`);
                        }
                        currentCategory = category;
                    }
                    else if (line.indexOf('<') !== -1 || line.indexOf('>') !== -1) {
                        isValid = false;
                        validationMessages.push(`Satır ${index + 1}: "${line}" geçersiz HTML karakterleri içeriyor (< veya >)`);
                    }
                });
                
                let resultAlert;
                if (isValid) {
                    resultAlert = document.createElement('div');
                    resultAlert.className = 'alert alert-success alert-dismissible fade show mt-3';
                    resultAlert.innerHTML = `
                        <i class="bi bi-check-circle-fill me-2"></i>
                        <strong>Doğrulama Başarılı!</strong> Anahtar kelimeler doğru formatta.
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    `;
                } else {
                    resultAlert = document.createElement('div');
                    resultAlert.className = 'alert alert-danger alert-dismissible fade show mt-3';
                    resultAlert.innerHTML = `
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        <strong>Doğrulama Hatası!</strong> Lütfen aşağıdaki hataları düzeltin:
                        <ul class="mt-2 mb-0">
                            ${validationMessages.map(msg => `<li>${msg}</li>`).join('')}
                        </ul>
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    `;
                }
                
                const existingAlert = document.querySelector('#keywordsForm .alert');
                if (existingAlert) {
                    existingAlert.remove();
                }
                
                document.getElementById('keywordsForm').insertAdjacentElement('afterend', resultAlert);
                
                setTimeout(() => {
                    if (resultAlert.parentNode) {
                        resultAlert.remove();
                    }
                }, 10000);
                
                return isValid;
            });
        }
        
        keywordsContentTextarea.addEventListener('keydown', function(e) {
            if (e.key === 'Tab') {
                e.preventDefault();
                
                const start = this.selectionStart;
                const end = this.selectionEnd;
                
                this.value = this.value.substring(0, start) + '    ' + this.value.substring(end);
                
                this.selectionStart = this.selectionEnd = start + 4;
            }
        });
    }
    
    const channelsForm = document.getElementById('channelsForm');
    if (channelsForm) {
        const editChannelsBtn = document.getElementById('editChannelsBtn');
        const cancelEditBtn = document.getElementById('cancelEditBtn');
        const validateBtn = document.getElementById('validateBtn');
        const channelsView = document.getElementById('channelsView');
        const channelsEdit = document.getElementById('channelsEdit');
        const contentTextarea = document.getElementById('content');
        
        if (contentTextarea) {
            const originalContent = contentTextarea.value;
            const channelSearch = document.getElementById('channelSearch');
            
            function cleanChannelsTextareaContent() {
                const lines = contentTextarea.value.split('\n');
                const cleanedLines = [];
                
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i].trim();
                    
                    if (line === '') {
                        continue;
                    }
                    
                    cleanedLines.push(line);
                }
                
                contentTextarea.value = cleanedLines.join('\n');
            }
            
            channelsForm.addEventListener('submit', function(e) {
                e.preventDefault();
                cleanChannelsTextareaContent();
                this.submit();
            });
            
            if (editChannelsBtn) {
                editChannelsBtn.addEventListener('click', function() {
                    channelsView.style.display = 'none';
                    channelsEdit.style.display = 'block';
                    contentTextarea.focus();
                    
                    window.scrollTo({
                        top: 0,
                        behavior: 'smooth'
                    });
                });
            }
            
            if (cancelEditBtn) {
                cancelEditBtn.addEventListener('click', function() {
                    if (contentTextarea.value !== originalContent) {
                        if (confirm('Değişiklikleriniz kaydedilmeyecek. Devam etmek istiyor musunuz?')) {
                            contentTextarea.value = originalContent;
                            channelsEdit.style.display = 'none';
                            channelsView.style.display = 'block';
                        }
                    } else {
                        channelsEdit.style.display = 'none';
                        channelsView.style.display = 'block';
                    }
                });
            }
            
            if (validateBtn) {
                validateBtn.addEventListener('click', function() {
                    cleanChannelsTextareaContent();
                    
                    const content = contentTextarea.value.trim();
                    let isValid = true;
                    let validationMessages = [];
                    let validChannelCount = 0;
                    
                    const lines = content.split('\n');
                    
                    lines.forEach((line, index) => {
                        line = line.trim();
                        
                        if (line === '' || line.startsWith('#')) {
                            return;
                        }
                        
                        if (!line.startsWith('https://t.me/') && !line.startsWith('@')) {
                            isValid = false;
                            validationMessages.push(`Satır ${index + 1}: "${line}" geçersiz Grup formatı. "https://t.me/Grupadi" veya "@Grupadi" formatında olmalıdır.`);
                        } else {
                            validChannelCount++;
                        }
                    });
                    
                    let resultAlert;
                    if (isValid) {
                        resultAlert = document.createElement('div');
                        resultAlert.className = 'alert alert-success alert-dismissible fade show mt-3';
                        resultAlert.innerHTML = `
                            <i class="bi bi-check-circle-fill me-2"></i>
                            <strong>Doğrulama Başarılı!</strong> ${validChannelCount} adet geçerli Grup bulundu.
                            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                        `;
                    } else {
                        resultAlert = document.createElement('div');
                        resultAlert.className = 'alert alert-danger alert-dismissible fade show mt-3';
                        resultAlert.innerHTML = `
                            <i class="bi bi-exclamation-triangle-fill me-2"></i>
                            <strong>Doğrulama Hatası!</strong> Lütfen aşağıdaki hataları düzeltin:
                            <ul class="mt-2 mb-0">
                                ${validationMessages.map(msg => `<li>${msg}</li>`).join('')}
                            </ul>
                            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                        `;
                    }
                    
                    const existingAlert = document.querySelector('#channelsForm .alert');
                    if (existingAlert) {
                        existingAlert.remove();
                    }
                    
                    document.getElementById('channelsForm').insertAdjacentElement('afterend', resultAlert);
                    
                    setTimeout(() => {
                        if (resultAlert.parentNode) {
                            resultAlert.remove();
                        }
                    }, 10000);
                    
                    return isValid;
                });
            }
            
            if (channelSearch) {
                channelSearch.addEventListener('keyup', function() {
                    const searchText = this.value.toLowerCase();
                    const channelItems = document.querySelectorAll('.channel-item');
                    let visibleCount = 0;
                    
                    channelItems.forEach(item => {
                        const channelName = item.querySelector('.channel-link').textContent.trim().toLowerCase();
                        if (channelName.includes(searchText)) {
                            item.style.display = '';
                            visibleCount++;
                        } else {
                            item.style.display = 'none';
                        }
                    });
                    
                    let noResultsMessage = document.getElementById('noChannelsFound');
                    
                    if (visibleCount === 0 && searchText !== '') {
                        if (!noResultsMessage) {
                            noResultsMessage = document.createElement('div');
                            noResultsMessage.id = 'noChannelsFound';
                            noResultsMessage.className = 'list-group-item text-center text-muted py-4';
                            noResultsMessage.innerHTML = `
                                <i class="bi bi-search display-4 d-block mb-3"></i>
                                <h5>Sonuç Bulunamadı</h5>
                                <p>Aramanızla eşleşen Grup bulunamadı.</p>
                            `;
                            document.getElementById('channelsList').appendChild(noResultsMessage);
                        }
                    } else if (noResultsMessage) {
                        noResultsMessage.remove();
                    }
                });
            }
        }
    }
    
    const enabledCheckbox = document.getElementById('email_enabled');
    if (enabledCheckbox) {
        const emailSettings = document.getElementById('emailSettings');
        
        enabledCheckbox.addEventListener('change', function() {
            if (this.checked) {
                emailSettings.classList.remove('d-none');
                emailSettings.classList.add('d-block');
            } else {
                emailSettings.classList.remove('d-block');
                emailSettings.classList.add('d-none');
            }
        });
    }
    
    const togglePasswordBtn = document.getElementById('togglePassword');
    if (togglePasswordBtn) {
        const passwordInput = document.getElementById('email_password');
        
        togglePasswordBtn.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            
            const eyeIcon = this.querySelector('i');
            eyeIcon.classList.toggle('bi-eye');
            eyeIcon.classList.toggle('bi-eye-slash');
        });
    }
    
    const emailForm = document.getElementById('emailForm');
    if (emailForm) {
        const saveButton = document.getElementById('saveButton');
        
        emailForm.addEventListener('submit', function(e) {
            saveButton.disabled = true;
            saveButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Kaydediliyor...';
        });
    }
    
    const emailToInput = document.getElementById('email_to');
    if (emailToInput) {
        emailToInput.addEventListener('keyup', function(e) {
            if (e.key === ',') {
                const emails = this.value.split(',');
                const lastEmail = emails[emails.length - 2]?.trim();
                
                if (lastEmail && !isValidEmail(lastEmail)) {
                    this.classList.add('is-invalid');
                    
                    if (!document.getElementById('email-validation-message')) {
                        const validationMessage = document.createElement('div');
                        validationMessage.id = 'email-validation-message';
                        validationMessage.className = 'invalid-feedback';
                        validationMessage.textContent = `"${lastEmail}" geçerli bir e-posta adresi değil.`;
                        this.parentNode.appendChild(validationMessage);
                    } else {
                        document.getElementById('email-validation-message').textContent = `"${lastEmail}" geçerli bir e-posta adresi değil.`;
                    }
                } else {
                    this.classList.remove('is-invalid');
                    const validationMessage = document.getElementById('email-validation-message');
                    if (validationMessage) {
                        validationMessage.remove();
                    }
                }
            }
        });
    }
    
    function isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    const statsPage = document.getElementById('alertTrendChart') && document.getElementById('stats-loading');
    if (statsPage) {
        const today = new Date();
        const todayStr = today.toISOString().substr(0, 10);
        
        const startDateInput = document.getElementById('startDate');
        const endDateInput = document.getElementById('endDate');
        
        if (startDateInput && endDateInput) {
            endDateInput.max = todayStr;
            startDateInput.max = todayStr;
            
            endDateInput.value = todayStr;
            
            const sevenDaysAgo = new Date();
            sevenDaysAgo.setDate(today.getDate() - 7);
            startDateInput.value = sevenDaysAgo.toISOString().substr(0, 10);
        }
        
        let trendChart = null;
        let categoryChart = null;
        let channelChart = null;
        let hourlyChart = null;
        
        const chartColors = {
            primary: 'rgba(0, 136, 204, 1)',
            primaryLight: 'rgba(0, 136, 204, 0.2)',
            success: 'rgba(46, 204, 113, 1)',
            warning: 'rgba(243, 156, 18, 1)',
            danger: 'rgba(231, 76, 60, 1)',
            info: 'rgba(52, 152, 219, 1)',
            secondary: 'rgba(108, 117, 125, 1)',
            categoryColors: [
                'rgba(255, 99, 132, 1)',
                'rgba(54, 162, 235, 1)',
                'rgba(255, 206, 86, 1)',
                'rgba(75, 192, 192, 1)',
                'rgba(153, 102, 255, 1)',
                'rgba(255, 159, 64, 1)',
                'rgba(255, 99, 255, 1)',
                'rgba(54, 162, 64, 1)',
                'rgba(192, 206, 86, 1)',
                'rgba(75, 192, 255, 1)'
            ]
        };
        
        function formatNumber(num) {
            return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        
        function showLoading() {
            document.getElementById('stats-loading').classList.remove('d-none');
            document.getElementById('stats-content').classList.add('d-none');
        }
        
        function hideLoading() {
            document.getElementById('stats-loading').classList.add('d-none');
            document.getElementById('stats-content').classList.remove('d-none');
        }
        
        function loadData(range = 7) {
            let alertsData = [];
            
            showLoading();
            
            fetch('/alerts')
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Uyarılar yüklenirken bir hata oluştu');
                    }
                    return response.json();
                })
                .then(data => {
                    alertsData = data;
                    hideLoading();
                    processData(alertsData, range);
                })
                .catch(error => {
                    hideLoading();
                    
                    const errorAlert = document.createElement('div');
                    errorAlert.className = 'alert alert-danger alert-dismissible fade show';
                    errorAlert.innerHTML = `
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        <strong>Hata:</strong> ${error.message || 'Veriler yüklenirken bir hata oluştu'}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    `;
                    document.querySelector('.page-header').insertAdjacentElement('afterend', errorAlert);
                });
        }
        
        function processData(alerts, range = 7) {
            let categories = new Set();
            let channels = new Set();

            const today = new Date();
            today.setHours(23, 59, 59, 999);
            
            const startDate = new Date();
            startDate.setDate(today.getDate() - range);
            startDate.setHours(0, 0, 0, 0);
            
            const filteredAlerts = alerts.filter(alert => {
                const alertDate = new Date(alert.timestamp);
                return alertDate >= startDate && alertDate <= today;
            });
            
            filteredAlerts.forEach(alert => {
                if (alert.categories) {
                    alert.categories.forEach(category => categories.add(category));
                }
                
                if (alert.chat) {
                    channels.add(alert.chat);
                }
            });
            
            const totalAlertCount = document.getElementById('totalAlertCount');
            const categoryCount = document.getElementById('categoryCount');
            const channelCount = document.getElementById('channelCount');
            
            if (totalAlertCount && categoryCount && channelCount) {
                totalAlertCount.textContent = formatNumber(alerts.length);
                categoryCount.textContent = formatNumber(categories.size);
                channelCount.textContent = formatNumber(channels.size);
            }
            
            const todayStart = new Date();
            todayStart.setHours(0, 0, 0, 0);
            
            const todayAlerts = alerts.filter(alert => {
                const alertDate = new Date(alert.timestamp);
                return alertDate >= todayStart;
            });
            
            const todayAlertCount = document.getElementById('todayAlertCount');
            if (todayAlertCount) {
                todayAlertCount.textContent = formatNumber(todayAlerts.length);
            }
            
            const yesterdayStart = new Date();
            yesterdayStart.setDate(yesterdayStart.getDate() - 1);
            yesterdayStart.setHours(0, 0, 0, 0);
            
            const yesterdayEnd = new Date();
            yesterdayEnd.setDate(yesterdayEnd.getDate() - 1);
            yesterdayEnd.setHours(23, 59, 59, 999);
            
            const yesterdayAlerts = alerts.filter(alert => {
                const alertDate = new Date(alert.timestamp);
                return alertDate >= yesterdayStart && alertDate <= yesterdayEnd;
            });
            
            const todayPercentage = document.getElementById('todayPercentage');
            if (todayPercentage && yesterdayAlerts.length > 0) {
                const percentageChange = ((todayAlerts.length - yesterdayAlerts.length) / yesterdayAlerts.length) * 100;
                
                if (percentageChange > 0) {
                    todayPercentage.className = 'text-success';
                    todayPercentage.innerHTML = `<i class="bi bi-arrow-up"></i> ${percentageChange.toFixed(1)}%`;
                } else if (percentageChange < 0) {
                    todayPercentage.className = 'text-danger';
                    todayPercentage.innerHTML = `<i class="bi bi-arrow-down"></i> ${Math.abs(percentageChange).toFixed(1)}%`;
                } else {
                    todayPercentage.className = 'text-muted';
                    todayPercentage.innerHTML = `<i class="bi bi-dash"></i> 0%`;
                }
            }
            
            generateTrendChart(filteredAlerts);
            generateCategoryChart(filteredAlerts);
            generateChannelChart(filteredAlerts);
            generateHourlyChart(filteredAlerts);
        }
        
        function generateTrendChart(alerts) {
            if (trendChart) {
                trendChart.destroy();
            }
            
            const dates = [];
            const counts = [];
            
            for (let i = 6; i >= 0; i--) {
                const date = new Date();
                date.setDate(date.getDate() - i);
                date.setHours(0, 0, 0, 0);
                
                const nextDate = new Date(date);
                nextDate.setDate(nextDate.getDate() + 1);
                
                const dateString = date.toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' });
                
                const dayAlerts = alerts.filter(alert => {
                    const alertDate = new Date(alert.timestamp);
                    return alertDate >= date && alertDate < nextDate;
                });
                
                dates.push(dateString);
                counts.push(dayAlerts.length);
            }
            
            const ctx = document.getElementById('alertTrendChart').getContext('2d');
            trendChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [{
                        label: 'Uyarı Sayısı',
                        data: counts,
                        backgroundColor: chartColors.primaryLight,
                        borderColor: chartColors.primary,
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true,
                        pointBackgroundColor: '#fff',
                        pointBorderColor: chartColors.primary,
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0,0,0,0.7)',
                            padding: 10,
                            titleFont: {
                                size: 14
                            },
                            bodyFont: {
                                size: 14
                            },
                            callbacks: {
                                label: function(context) {
                                    return `Uyarı Sayısı: ${context.raw}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0,0,0,0.05)'
                            },
                            ticks: {
                                precision: 0,
                                font: {
                                    size: 12
                                }
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                font: {
                                    size: 12
                                }
                            }
                        }
                    }
                }
            });
        }
        
        function generateCategoryChart(alerts) {
            if (categoryChart) {
                categoryChart.destroy();
            }
            
            const categoryData = {};
            
            alerts.forEach(alert => {
                if (alert.categories && alert.categories.length > 0) {
                    alert.categories.forEach(category => {
                        if (!categoryData[category]) {
                            categoryData[category] = 0;
                        }
                        categoryData[category]++;
                    });
                } else {
                    if (!categoryData["Diğer"]) {
                        categoryData["Diğer"] = 0;
                    }
                    categoryData["Diğer"]++;
                }
            });
            
            const sortedCategories = Object.entries(categoryData)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 8);
            
            const remainingCategories = Object.entries(categoryData)
                .sort((a, b) => b[1] - a[1])
                .slice(8);
            
            if (remainingCategories.length > 0) {
                const otherCount = remainingCategories.reduce((sum, item) => sum + item[1], 0);
                if (otherCount > 0) {
                    sortedCategories.push(["Diğer", otherCount]);
                }
            }
            
            const labels = sortedCategories.map(item => item[0]);
            const data = sortedCategories.map(item => item[1]);
            
            const backgroundColors = chartColors.categoryColors.slice(0, data.length);
            
            const ctx = document.getElementById('categoryChart').getContext('2d');
            categoryChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: data,
                        backgroundColor: backgroundColors,
                        borderColor: '#fff',
                        borderWidth: 2,
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '65%',
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0,0,0,0.7)',
                            padding: 10,
                            titleFont: {
                                size: 14
                            },
                            bodyFont: {
                                size: 14
                            },
                            callbacks: {
                                label: function(context) {
                                    const value = context.raw;
                                    const total = context.chart.data.datasets[0].data.reduce((sum, val) => sum + val, 0);
                                    const percentage = Math.round((value / total) * 100);
                                    return `${context.label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
            
            const legendContainer = document.getElementById('categoryLegend');
            if (legendContainer) {
                legendContainer.innerHTML = '';
                
                labels.forEach((label, i) => {
                    const percentage = Math.round((data[i] / data.reduce((sum, val) => sum + val, 0)) * 100);
                    const legendItem = document.createElement('div');
                    legendItem.className = 'me-3 mb-1';
                    legendItem.innerHTML = `
                        <div class="d-flex align-items-center">
                            <div style="width: 12px; height: 12px; background-color: ${backgroundColors[i]}; margin-right: 5px; border-radius: 2px;"></div>
                            <small>${label} (${percentage}%)</small>
                        </div>
                    `;
                    legendContainer.appendChild(legendItem);
                });
            }
        }
        
        function generateChannelChart(alerts) {
            if (channelChart) {
                channelChart.destroy();
            }
            
            const channelData = {};
            
            alerts.forEach(alert => {
                if (!channelData[alert.chat]) {
                    channelData[alert.chat] = 0;
                }
                channelData[alert.chat]++;
            });
            
            const sortedChannels = Object.entries(channelData)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10);
            
            const labels = sortedChannels.map(item => {
                const channelName = item[0];
                return channelName.length > 25 ? channelName.substring(0, 22) + '...' : channelName;
            });
            const data = sortedChannels.map(item => item[1]);
            
            const ctx = document.getElementById('channelChart').getContext('2d');
            channelChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Uyarı Sayısı',
                        data: data,
                        backgroundColor: chartColors.info,
                        borderColor: chartColors.info,
                        borderWidth: 1,
                        borderRadius: 4,
                        barPercentage: 0.5,
                        categoryPercentage: 0.8
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0,0,0,0.7)',
                            padding: 10,
                            titleFont: {
                                size: 14
                            },
                            bodyFont: {
                                size: 14
                            },
                            callbacks: {
                                title: function(tooltipItems) {
                                    const originalName = sortedChannels[tooltipItems[0].dataIndex][0];
                                    return originalName;
                                },
                                label: function(context) {
                                    return `Uyarı Sayısı: ${context.raw}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0,0,0,0.05)'
                            },
                            ticks: {
                                precision: 0,
                                font: {
                                    size: 12
                                }
                            }
                        },
                        y: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                font: {
                                    size: 12
                                }
                            }
                        }
                    }
                }
            });
        }
        
        function generateHourlyChart(alerts) {
            if (hourlyChart) {
                hourlyChart.destroy();
            }
            
            const hourlyData = Array(24).fill(0);
            
            alerts.forEach(alert => {
                const date = new Date(alert.timestamp);
                const hour = date.getHours();
                hourlyData[hour]++;
            });
            
            const labels = Array.from({length: 24}, (_, i) => i);
            
            const gradientFill = ctx => {
                const gradient = ctx.createLinearGradient(0, 0, 0, 300);
                gradient.addColorStop(0, 'rgba(75, 192, 192, 0.6)');
                gradient.addColorStop(1, 'rgba(75, 192, 192, 0.1)');
                return gradient;
            };
            
            const ctx = document.getElementById('hourlyChart').getContext('2d');
            
            hourlyChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Uyarı Sayısı',
                        data: hourlyData,
                        backgroundColor: function(context) {
                            const chart = context.chart;
                            const {ctx, chartArea} = chart;
                            if (!chartArea) {
                                return null;
                            }
                            return gradientFill(ctx);
                        },
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#fff',
                        pointBorderColor: 'rgba(75, 192, 192, 1)',
                        pointBorderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0,0,0,0.7)',
                            padding: 10,
                            titleFont: {
                                size: 14
                            },
                            bodyFont: {
                                size: 14
                            },
                            callbacks: {
                                title: function(tooltipItems) {
                                    const hour = tooltipItems[0].label;
                                    return `Saat: ${hour}:00 - ${hour}:59`;
                                },
                                label: function(context) {
                                    return `Uyarı Sayısı: ${context.raw}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0,0,0,0.05)'
                            },
                            ticks: {
                                precision: 0,
                                font: {
                                    size: 12
                                }
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                callback: function(val, index) {
                                    return index % 4 === 0 ? `${val}:00` : '';
                                },
                                font: {
                                    size: 12
                                }
                            }
                        }
                    }
                }
            });
        }
        
        const refreshStatsBtn = document.getElementById('refreshStats');
        if (refreshStatsBtn) {
            refreshStatsBtn.addEventListener('click', function() {
                const range = parseInt(document.querySelector('.dropdown-item.active').getAttribute('data-range'));
                loadData(range);
                
                const toast = document.createElement('div');
                toast.className = 'alert alert-success alert-dismissible fade show position-fixed bottom-0 end-0 m-3';
                toast.style.zIndex = '1050';
                toast.innerHTML = `
                    <i class="bi bi-check-circle-fill me-2"></i>
                    İstatistikler yenilendi
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                document.body.appendChild(toast);
                
                setTimeout(() => {
                    toast.remove();
                }, 3000);
            });
        }
        
        const dateRangeItems = document.querySelectorAll('.dropdown-item[data-range]');
        dateRangeItems.forEach(item => {
            item.addEventListener('click', function() {
                dateRangeItems.forEach(i => i.classList.remove('active'));
                
                this.classList.add('active');
                
                const rangeText = this.innerText;
                const dateRangeDropdown = document.getElementById('dateRangeDropdown');
                if (dateRangeDropdown) {
                    dateRangeDropdown.innerText = rangeText;
                }
                
                if (this.getAttribute('data-range') === 'custom') {
                    const dateRangeModal = new bootstrap.Modal(document.getElementById('dateRangeModal'));
                    dateRangeModal.show();
                } else {
                    const range = parseInt(this.getAttribute('data-range'));
                    loadData(range);
                }
            });
        });
        
        const applyDateRangeBtn = document.getElementById('applyDateRange');
        if (applyDateRangeBtn) {
            applyDateRangeBtn.addEventListener('click', function() {
                const startDate = new Date(document.getElementById('startDate').value);
                const endDate = new Date(document.getElementById('endDate').value);
                
                if (startDate > endDate) {
                    alert('Başlangıç tarihi, bitiş tarihinden sonra olamaz.');
                    return;
                }
                
                const diffTime = Math.abs(endDate - startDate);
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
                
                const dateRangeDropdown = document.getElementById('dateRangeDropdown');
                if (dateRangeDropdown) {
                    dateRangeDropdown.innerHTML = `<i class="bi bi-calendar3 me-1"></i> Özel: ${startDate.toLocaleDateString('tr-TR')} - ${endDate.toLocaleDateString('tr-TR')}`;
                }
                
                loadData(diffDays);
                
                const dateRangeModal = bootstrap.Modal.getInstance(document.getElementById('dateRangeModal'));
                dateRangeModal.hide();
            });
        }
        
        const chartViewButtons = document.querySelectorAll('[data-chart-view]');
        chartViewButtons.forEach(button => {
            button.addEventListener('click', function() {
                chartViewButtons.forEach(btn => btn.classList.remove('active'));
                
                this.classList.add('active');
                
                alert('Bu özellik henüz uygulanmamıştır.');
            });
        });
        
        loadData(7);
    }
});