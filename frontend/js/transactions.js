<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Sentinel — Transactions</title>

    <link
        rel="stylesheet"
        href="../css/style.css"
    >

</head>


<body data-page="transactions">

<div class="app">

    <aside
        class="sidebar"
        id="sidebar"
    ></aside>


    <main class="main">

        <div class="page-header">

            <div>
                <h1 class="page-title">
                    Transactions
                </h1>

                <div class="page-subtitle">
                    Live transaction risk monitoring
                </div>
            </div>

            <div class="status">
                <span class="status-dot"></span>
                Live Feed
            </div>

        </div>


        <div class="panel">

            <div class="panel-title">
                Recent Transaction Activity
            </div>

            <table>

                <thead>

                    <tr>
                        <th>Transaction</th>
                        <th>Amount</th>
                        <th>Risk</th>
                        <th>Level</th>
                        <th>Decision</th>
                        <th>Region</th>
                    </tr>

                </thead>

                <tbody id="transactionTable"></tbody>

            </table>

        </div>

    </main>

</div>


<script src="../js/app.js"></script>


<script>

async function loadTransactions() {

    try {

        const data =
            await api(
                "/api/transactions/recent?limit=100"
            );

        document.getElementById(
            "transactionTable"
        ).innerHTML =
            data.transactions.map(
                tx => `
                    <tr>

                        <td>
                            ${tx.transaction_id}
                        </td>

                        <td>
                            ${money(tx.amount)}
                        </td>

                        <td>
                            ${Number(
                                tx.risk_score
                            ).toFixed(2)}
                        </td>

                        <td>
                            ${badge(tx.risk_level)}
                        </td>

                        <td>
                            ${badge(tx.decision)}
                        </td>

                        <td>
                            ${tx.region_key || "—"}
                        </td>

                    </tr>
                `
            ).join("");

    } catch (error) {

        console.error(error);

    }
}


loadTransactions();

setInterval(
    loadTransactions,
    5000
);

</script>

</body>

</html>