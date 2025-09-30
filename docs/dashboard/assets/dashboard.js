
// ダッシュボードJavaScript
function initializeDashboard(data) {
    // 円形プログレスバーの初期化
    initializeCircularProgress();
    
    // チャートの初期化
    initializeCharts(data);
    
    // アニメーションの初期化
    initializeAnimations();
}

function initializeCircularProgress() {
    const progressElements = document.querySelectorAll('.circular-progress');
    progressElements.forEach(element => {
        const progress = element.getAttribute('data-progress');
        element.style.setProperty('--progress', progress);
    });
}

function initializeCharts(data) {
    // スキルチャート
    const skillsCtx = document.getElementById('skillsChart');
    if (skillsCtx) {
        new Chart(skillsCtx, {
            type: 'radar',
            data: {
                labels: Object.keys(data.technical_skills.core_technologies),
                datasets: [{
                    label: 'スキルレベル',
                    data: Object.values(data.technical_skills.core_technologies).map(skill => skill.level),
                    borderColor: 'rgb(102, 126, 234)',
                    backgroundColor: 'rgba(102, 126, 234, 0.2)',
                    pointBackgroundColor: 'rgb(102, 126, 234)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgb(102, 126, 234)'
                }]
            },
            options: {
                elements: {
                    line: {
                        borderWidth: 3
                    }
                },
                scales: {
                    r: {
                        angleLines: {
                            display: false
                        },
                        suggestedMin: 0,
                        suggestedMax: 100
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    // カバレッジチャート
    const coverageCtx = document.getElementById('coverageChart');
    if (coverageCtx) {
        new Chart(coverageCtx, {
            type: 'line',
            data: {
                labels: ['開始', 'Week1', 'Week2', '現在'],
                datasets: [{
                    label: 'カバレッジ',
                    data: data.quality_metrics.test_coverage.trend,
                    borderColor: 'rgb(76, 175, 80)',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    // パフォーマンスチャート
    const performanceCtx = document.getElementById('performanceChart');
    if (performanceCtx) {
        new Chart(performanceCtx, {
            type: 'bar',
            data: {
                labels: ['平均', 'P95', '目標'],
                datasets: [{
                    label: 'レスポンス時間(秒)',
                    data: [
                        data.quality_metrics.performance_metrics.response_time.average,
                        data.quality_metrics.performance_metrics.response_time.p95,
                        data.quality_metrics.performance_metrics.response_time.target
                    ],
                    backgroundColor: ['#4CAF50', '#FF9800', '#f44336']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
}

function initializeAnimations() {
    // スクロールアニメーション
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    // 各セクションを監視
    document.querySelectorAll('section').forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(20px)';
        section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(section);
    });
    
    // プログレスバーアニメーション
    const progressBars = document.querySelectorAll('.progress-fill, .skill-fill');
    progressBars.forEach(bar => {
        const width = bar.style.width;
        bar.style.width = '0';
        setTimeout(() => {
            bar.style.width = width;
        }, 500);
    });
}

// ユーティリティ関数
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ja-JP');
}

function formatNumber(number) {
    return number.toLocaleString('ja-JP');
}

// エクスポート用関数
function exportDashboard() {
    window.print();
}

// データ更新関数
function updateDashboardData(newData) {
    window.portfolioData = newData;
    location.reload();
}
