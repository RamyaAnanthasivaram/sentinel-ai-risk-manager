<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Sentinel — Incidents</title>

    <link
        rel="stylesheet"
        href="../css/style.css"
    >

</head>


<body data-page="incidents">

<div class="app">

    <aside
        class="sidebar"
        id="sidebar"
    ></aside>


    <main class="main">

        <div class="page-header">

            <div>
                <h1 class="page-title">
                    Incidents
                </h1>

                <div class="page-subtitle">
                    Risk incidents detected by Sentinel
                </div>
            </div>

            <div class="status">
                <span class="status-dot"></span>
                Monitoring
            </div>

        </div>


        <div id="incidentList"></div>

    </main>

</div>


<script src="../js/app.js"></script>


<script>

async function loadIncidents() {

    try {

        const data =
            await api(
                "/api/incidents"
            );

        const container =
            document.getElementById(
                "incidentList"
            );

        if (!data.incidents.length) {

            container.innerHTML =
                `
                <div class="panel">
                    <div class="empty">
                        No incidents detected.
                    </div>
                </div>
                `;

            return;
        }

        container.innerHTML =
            data.incidents.map(
                incident => `

                    <div class="panel"
                         style="margin-bottom:18px">

                        <div
                            style="
                                display:flex;
                                justify-content:space-between;
                                align-items:center;
                            "
                        >

                            <div>

                                <div
                                    style="
                                        font-size:20px;
                                        font-weight:750;
                                    "
                                >
                                    ${incident.incident_id}
                                </div>

                                <div
                                    class="note"
                                >
                                    ${incident.incident_type}
                                </div>

                            </div>

                            <div>
                                ${badge(
                                    incident.severity
                                )}

                                ${badge(
                                    incident.status
                                )}
                            </div>

                        </div>


                        <div class="metric-row">

                            <div class="metric">
                                <div class="metric-label">
                                    REGION
                                </div>

                                <div
                                    class="metric-value"
                                >
                                    ${incident.region_key}
                                </div>
                            </div>


                            <div class="metric">
                                <div class="metric-label">
                                    AFFECTED
                                </div>

                                <div
                                    class="metric-value"
                                >
                                    ${incident.affected_transactions}
                                </div>
                            </div>


                            <div class="metric">
                                <div class="metric-label">
                                    Z-SCORE
                                </div>

                                <div
                                    class="metric-value"
                                >
                                    ${Number(
                                        incident.z_score
                                    ).toFixed(2)}
                                </div>
                            </div>


                            <div class="metric">
                                <div class="metric-label">
                                    RATE RATIO
                                </div>

                                <div
                                    class="metric-value"
                                >
                                    ${Number(
                                        incident.rate_ratio
                                    ).toFixed(1)}×
                                </div>
                            </div>

                        </div>


                        <div class="note">
                            Baseline:
                            ${(
                                incident.baseline_rate
                                * 100
                            ).toFixed(2)}%

                            →

                            Current:
                            ${(
                                incident.current_rate
                                * 100
                            ).toFixed(2)}%
                        </div>


                        <div class="note">
                            Exposure:
                            ${money(
                                incident.total_exposure
                            )}
                        </div>


                        <div
                            class="note"
                            style="margin-top:14px"
                        >
                            ${incident.description}
                        </div>


                        <button
                            class="btn btn-primary"
                            style="margin-top:15px"
                            onclick="
                                alert(
                                    'Investigation page coming next.'
                                )
                            "
                        >
                            Investigate
                        </button>

                    </div>
                `
            ).join("");

    } catch (error) {

        console.error(error);

    }
}


loadIncidents();

setInterval(
    loadIncidents,
    10000
);

</script>

</body>

</html>