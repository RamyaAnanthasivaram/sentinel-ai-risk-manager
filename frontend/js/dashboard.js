<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Sentinel — Dashboard</title>

    <link
        rel="stylesheet"
        href="../css/style.css"
    >

</head>


<body data-page="dashboard">

<div class="app">

    <aside
        class="sidebar"
        id="sidebar"
    ></aside>


    <main class="main">

        <div class="page-header">

            <div>
                <h1 class="page-title">
                    Risk Dashboard
                </h1>

                <div class="page-subtitle">
                    Real-time payment risk operations
                </div>
            </div>

            <div class="status">
                <span class="status-dot"></span>
                Sentinel Online
            </div>

        </div>


        <section class="cards">

            <div class="card">
                <div class="card-label">
                    Transactions
                </div>

                <div
                    class="card-value"
                    id="total"
                >—</div>
            </div>

            <div class="card">
                <div class="card-label">
                    High Risk
                </div>

                <div
                    class="card-value"
                    id="highRisk"
                >—</div>
            </div>

            <div class="card">
                <div class="card-label">
                    Pending Reviews
                </div>

                <div
                    class="card-value"
                    id="reviews"
                >—</div>
            </div>

            <div class="card">
                <div class="card-label">
                    Blocked
                </div>

                <div
                    class="card-value"
                    id="blocked"
                >—</div>
            </div>

        </section>


        <section class="grid-2">

            <div class="panel">

                <div class="panel-title">
                    Recent Transactions
                </div>

                <table>

                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Amount</th>
                            <th>Risk</th>
                            <th>Decision</th>
                        </tr>
                    </thead>

                    <tbody id="transactions"></tbody>

                </table>

            </div>


            <div class="panel">

                <div class="panel-title">
                    Active Incidents
                </div>

                <div id="incidents"></div>

            </div>

        </section>

    </main>

</div>


<script src="../js/app.js"></script>


<script>

async function loadDashboard() {

    try {

        const stats =
            await api(
                "/api/dashboard/stats"
            );

        document
            .getElementById("total")
            .textContent =
            stats.total_transactions;

        document
            .getElementById("highRisk")
            .textContent =
            stats.high_risk_transactions;

        document
            .getElementById("reviews")
            .textContent =
            stats.pending_reviews;

        document
            .getElementById("blocked")
            .textContent =
            stats.blocked_transactions;


        const tx =
            await api(
                "/api/transactions/recent?limit=10"
            );

        document.getElementById(
            "transactions"
        ).innerHTML =
            tx.transactions.map(
                item => `
                    <tr>

                        <td>
                            ${item.transaction_id}
                        </td>

                        <td>
                            ${money(item.amount)}
                        </td>

                        <td>
                            ${Number(
                                item.risk_score
                            ).toFixed(2)}
                        </td>

                        <td>
                            ${badge(
                                item.decision
                            )}
                        </td>

                    </tr>
                `
            ).join("");


        const incidentData =
            await api(
                "/api/incidents"
            );

        const openIncidents =
            incidentData.incidents
                .filter(
                    i => i.status === "OPEN"
                );

        const container =
            document.getElementById(
                "incidents"
            );

        if (!openIncidents.length) {

            container.innerHTML =
                `<div class="empty">
                    No active incidents.
                </div>`;

        } else {

            container.innerHTML =
                openIncidents.map(
                    i => `
                        <div class="incident-card">

                            <h3>
                                ${i.incident_id}
                            </h3>

                            <div>
                                ${i.incident_type}
                                ${badge(i.severity)}
                            </div>

                            <div class="note">
                                Region:
                                ${i.region_key}
                            </div>

                            <button
                                class="btn btn-primary"
                                style="margin-top:12px"
                                onclick="
                                    location.href =
                                    'incidents.html'
                                "
                            >
                                Investigate
                            </button>

                        </div>
                    `
                ).join("");
        }

    } catch (error) {

        console.error(error);

    }
}


loadDashboard();

setInterval(
    loadDashboard,
    5000
);

</script>

</body>

</html>