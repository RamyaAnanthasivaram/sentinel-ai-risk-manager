const API = "http://127.0.0.1:8001";


/* =========================================================
   SIDEBAR
   ========================================================= */

function mountSidebar() {

    const sidebar =
        document.getElementById("sidebar");

    if (!sidebar) {
        return;
    }


    sidebar.innerHTML = `

        <div class="logo">

            <div class="logo-title">
                SENTINEL
            </div>

            <div class="logo-subtitle">
                AI RISK MANAGER
            </div>

        </div>


        <div class="nav-section">
            OVERVIEW
        </div>


        <a
            class="nav-link"
            href="dashboard.html"
            data-page="dashboard"
        >
            <span class="nav-icon">🏠</span>
            Dashboard
        </a>


        <div class="nav-section">
            RISK
        </div>


        <a
            class="nav-link"
            href="transactions.html"
            data-page="transactions"
        >
            <span class="nav-icon">💳</span>
            Transactions
        </a>


        <!-- SIMULATE TRANSACTION -->

        <a
            class="nav-link"
            href="simulate.html"
            data-page="simulate"
        >

            <img
                class="nav-image-icon"
                src="../assets/billing.png"
                alt=""
            >

            <span>
                Simulate Transaction
            </span>

        </a>


        <a
            class="nav-link"
            href="regional.html"
            data-page="regional"
        >
            <span class="nav-icon">🌍</span>
            Regional Risk
        </a>


        <a
            class="nav-link"
            href="spikes.html"
            data-page="spikes"
        >
            <span class="nav-icon">📈</span>
            Fraud Spikes
        </a>


        <div class="nav-section">
            OPERATIONS
        </div>


        <a
            class="nav-link"
            href="incidents.html"
            data-page="incidents"
        >
            <span class="nav-icon">🚨</span>
            Incidents
        </a>


        <a
            class="nav-link"
            href="investigations.html"
            data-page="investigations"
        >
            <span class="nav-icon">🔎</span>
            Investigations
        </a>


        <a
            class="nav-link"
            href="reviews.html"
            data-page="reviews"
        >
            <span class="nav-icon">👤</span>
            Human Review
        </a>


        <div class="nav-section">
            GOVERNANCE
        </div>


        <a
            class="nav-link"
            href="audit.html"
            data-page="audit"
        >
            <span class="nav-icon">📋</span>
            Audit Log
        </a>


        <a
            class="nav-link"
            href="policy.html"
            data-page="policy"
        >
            <span class="nav-icon">⚙️</span>
            Policy & Thresholds
        </a>


        <a
            class="nav-link"
            href="health.html"
            data-page="health"
        >
            <span class="nav-icon">🩺</span>
            System Health
        </a>

    `;


    const page =
        document.body.dataset.page;


    document
        .querySelectorAll(".nav-link")
        .forEach(
            link => {

                if (
                    link.dataset.page ===
                    page
                ) {

                    link.classList.add(
                        "active"
                    );

                }

            }
        );

}


/* =========================================================
   API HELPER
   ========================================================= */

async function api(path) {

    const response =
        await fetch(
            API + path
        );


    if (!response.ok) {

        throw new Error(
            `${response.status}: ${path}`
        );

    }


    return response.json();

}


/* =========================================================
   UI HELPERS
   ========================================================= */

function badge(value) {

    return `
        <span class="badge ${value}">
            ${value}
        </span>
    `;

}


function money(value) {

    return (
        "₹" +
        Number(value || 0)
            .toLocaleString(
                "en-IN",
                {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                }
            )
    );

}


/* =========================================================
   START
   ========================================================= */

mountSidebar();