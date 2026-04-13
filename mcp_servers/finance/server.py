"""friday-finance MCP server.

Finance tracking: expenses, crypto prices, crypto portfolio.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("friday-finance")

DATA_DIR = Path.home() / ".local" / "share" / "friday" / "finance"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FINANCE_FILE = DATA_DIR / "expenses.json"


def _load() -> dict:
    if FINANCE_FILE.exists():
        try:
            return json.loads(FINANCE_FILE.read_text())
        except Exception:
            pass
    return {"expenses": [], "budgets": {}, "portfolio": {}}


def _save(data: dict) -> None:
    FINANCE_FILE.write_text(json.dumps(data, indent=2, default=str))


def _run(cmd: str, timeout: int = 15) -> str:
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip() or ""
    except subprocess.TimeoutExpired:
        return "Request timed out."
    except Exception as e:
        return f"Error: {e}"


def _now_month() -> str:
    return datetime.now().strftime("%Y-%m")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="expense",
            description=(
                "Track personal expenses. "
                "Actions:\n"
                "  'add' — add an expense (requires amount, category; optional note)\n"
                "  'list [month]' — list expenses (month format: YYYY-MM, default current)\n"
                "  'summary [month]' — spending by category\n"
                "  'budget' — set a budget for a category (requires category, amount)\n"
                "  'budgets' — show all budgets vs actual spend\n"
                "  'delete <id>' — remove an expense by id"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "list", "summary", "budget", "budgets", "delete"],
                    },
                    "amount": {"type": "number", "description": "Expense amount."},
                    "category": {"type": "string", "description": "Category (food, transport, entertainment, etc.)."},
                    "note": {"type": "string", "description": "Optional note/description."},
                    "month": {"type": "string", "description": "Month in YYYY-MM format (default: current month)."},
                    "id": {"type": "integer", "description": "Expense ID for delete action."},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="crypto_price",
            description=(
                "Check current crypto prices using CoinGecko API. "
                "Supports: BTC, ETH, XMR, BNB, SOL, ADA, DOT, MATIC, LINK, AVAX, and any CoinGecko coin ID. "
                "Currency defaults to USD."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "coins": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of coin symbols or CoinGecko IDs (e.g. ['BTC', 'ETH', 'XMR']).",
                        "default": ["BTC", "ETH", "XMR"],
                    },
                    "currency": {"type": "string", "default": "usd", "description": "Fiat currency (usd, eur, inr, etc.)."},
                },
            },
        ),
        Tool(
            name="crypto_portfolio",
            description=(
                "Track crypto holdings. "
                "Actions:\n"
                "  'add <coin> <amount>' — add/update holdings\n"
                "  'list' — show all holdings\n"
                "  'value' — calculate current total portfolio value\n"
                "  'remove <coin>' — remove a coin from portfolio"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "list", "value", "remove"]},
                    "coin": {"type": "string", "description": "Coin symbol (e.g. BTC, ETH, XMR)."},
                    "amount": {"type": "number", "description": "Amount held."},
                    "currency": {"type": "string", "default": "usd"},
                },
                "required": ["action"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "expense": _expense,
        "crypto_price": _crypto_price,
        "crypto_portfolio": _crypto_portfolio,
    }
    handler = handlers.get(name)
    result = handler(arguments) if handler else f"Unknown tool: {name}"
    return [TextContent(type="text", text=result)]


# ── Coin symbol -> CoinGecko ID mapping ──────────────────────────────────────
COIN_IDS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "xmr": "monero",
    "bnb": "binancecoin",
    "sol": "solana",
    "ada": "cardano",
    "dot": "polkadot",
    "matic": "matic-network",
    "link": "chainlink",
    "avax": "avalanche-2",
    "usdt": "tether",
    "usdc": "usd-coin",
    "doge": "dogecoin",
    "ltc": "litecoin",
    "atom": "cosmos",
    "xrp": "ripple",
}


def _resolve_coin_id(symbol: str) -> str:
    """Map a coin ticker symbol to a CoinGecko coin ID."""
    s = symbol.lower()
    return COIN_IDS.get(s, s)


def _fetch_prices(coin_ids: list[str], currency: str = "usd") -> dict:
    """Return {id: price} dict via CoinGecko simple price API."""
    ids_str = ",".join(coin_ids)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies={currency}&include_24hr_change=true"
    raw = _run(f"curl -s --max-time 10 '{url}'")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _expense(args: dict) -> str:
    action = args["action"]
    data = _load()

    if action == "add":
        amount = args.get("amount")
        category = args.get("category", "other")
        note = args.get("note", "")
        if amount is None:
            return "add requires 'amount'"
        entry = {
            "id": len(data["expenses"]) + 1,
            "amount": float(amount),
            "category": category.lower(),
            "note": note,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "month": datetime.now().strftime("%Y-%m"),
        }
        data["expenses"].append(entry)
        _save(data)
        return f"Added: {category} — ${amount:.2f}" + (f" ({note})" if note else "")

    elif action == "list":
        month = args.get("month", _now_month())
        month_expenses = [e for e in data["expenses"] if e.get("month") == month]
        if not month_expenses:
            return f"No expenses for {month}."
        lines = [f"Expenses for {month} ({len(month_expenses)} entries):\n"]
        total = 0.0
        for e in sorted(month_expenses, key=lambda x: x["date"]):
            lines.append(f"  [{e['id']}] {e['date']}  {e['category']:<15}  ${e['amount']:>8.2f}  {e.get('note', '')}")
            total += e["amount"]
        lines.append(f"\nTotal: ${total:.2f}")
        return "\n".join(lines)

    elif action == "summary":
        month = args.get("month", _now_month())
        month_expenses = [e for e in data["expenses"] if e.get("month") == month]
        if not month_expenses:
            return f"No expenses for {month}."
        by_cat: dict[str, float] = {}
        for e in month_expenses:
            cat = e.get("category", "other")
            by_cat[cat] = by_cat.get(cat, 0.0) + e["amount"]
        total = sum(by_cat.values())
        lines = [f"Summary for {month}:\n"]
        for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
            pct = amt / total * 100 if total else 0
            budget = data.get("budgets", {}).get(cat)
            budget_str = f"  (budget: ${budget:.0f}, {'OVER' if budget and amt > budget else 'OK'})" if budget else ""
            lines.append(f"  {cat:<20} ${amt:>8.2f}  {pct:5.1f}%{budget_str}")
        lines.append(f"\n  {'TOTAL':<20} ${total:>8.2f}")
        return "\n".join(lines)

    elif action == "budget":
        category = args.get("category")
        amount = args.get("amount")
        if not category or amount is None:
            return "budget requires category and amount"
        data.setdefault("budgets", {})[category.lower()] = float(amount)
        _save(data)
        return f"Budget set: {category} = ${amount:.2f}/month"

    elif action == "budgets":
        budgets = data.get("budgets", {})
        if not budgets:
            return "No budgets set."
        month = _now_month()
        month_expenses = [e for e in data["expenses"] if e.get("month") == month]
        by_cat: dict[str, float] = {}
        for e in month_expenses:
            cat = e.get("category", "other")
            by_cat[cat] = by_cat.get(cat, 0.0) + e["amount"]
        lines = [f"Budgets vs Actual ({month}):\n"]
        for cat, budget in sorted(budgets.items()):
            actual = by_cat.get(cat, 0.0)
            status = "OVER" if actual > budget else "OK  "
            bar_len = int(actual / budget * 20) if budget else 0
            bar = "#" * min(bar_len, 20) + "-" * max(0, 20 - bar_len)
            lines.append(f"  {cat:<15} [{bar}] ${actual:.0f}/${budget:.0f}  {status}")
        return "\n".join(lines)

    elif action == "delete":
        exp_id = args.get("id")
        if exp_id is None:
            return "delete requires 'id'"
        before = len(data["expenses"])
        data["expenses"] = [e for e in data["expenses"] if e.get("id") != int(exp_id)]
        if len(data["expenses"]) < before:
            _save(data)
            return f"Deleted expense #{exp_id}"
        return f"Expense #{exp_id} not found."

    return "Unknown action."


def _crypto_price(args: dict) -> str:
    raw_coins = args.get("coins", ["BTC", "ETH", "XMR"])
    currency = args.get("currency", "usd").lower()

    coin_ids = [_resolve_coin_id(c) for c in raw_coins]
    prices = _fetch_prices(coin_ids, currency)

    if not prices:
        return "Failed to fetch prices from CoinGecko. Check network connection."

    lines = [f"Crypto Prices (in {currency.upper()}):\n"]
    for symbol, coin_id in zip(raw_coins, coin_ids):
        data = prices.get(coin_id, {})
        price = data.get(currency)
        change = data.get(f"{currency}_24h_change")
        if price is None:
            lines.append(f"  {symbol.upper():<8}  not found")
        else:
            change_str = f"  {change:+.2f}% (24h)" if change is not None else ""
            lines.append(f"  {symbol.upper():<8}  ${price:>14,.2f}{change_str}")

    return "\n".join(lines)


def _crypto_portfolio(args: dict) -> str:
    action = args["action"]
    data = _load()
    portfolio: dict = data.setdefault("portfolio", {})

    if action == "add":
        coin = args.get("coin", "")
        amount = args.get("amount")
        if not coin or amount is None:
            return "add requires coin and amount"
        portfolio[coin.upper()] = float(amount)
        _save(data)
        return f"Portfolio updated: {coin.upper()} = {amount}"

    elif action == "remove":
        coin = args.get("coin", "").upper()
        if coin in portfolio:
            del portfolio[coin]
            _save(data)
            return f"Removed {coin} from portfolio."
        return f"{coin} not in portfolio."

    elif action == "list":
        if not portfolio:
            return "Portfolio is empty. Add coins with 'add'."
        lines = ["Portfolio:\n"]
        for coin, amount in sorted(portfolio.items()):
            lines.append(f"  {coin:<10}  {amount}")
        return "\n".join(lines)

    elif action == "value":
        if not portfolio:
            return "Portfolio is empty."
        currency = args.get("currency", "usd").lower()
        coin_ids = [_resolve_coin_id(c) for c in portfolio.keys()]
        prices = _fetch_prices(coin_ids, currency)

        if not prices:
            return "Failed to fetch prices. Cannot calculate portfolio value."

        lines = [f"Portfolio Value ({currency.upper()}):\n"]
        total = 0.0
        for (coin, amount), coin_id in zip(portfolio.items(), coin_ids):
            price_data = prices.get(coin_id, {})
            price = price_data.get(currency)
            if price is None:
                lines.append(f"  {coin:<10}  {amount}  (price unavailable)")
            else:
                value = amount * price
                total += value
                change = price_data.get(f"{currency}_24h_change")
                change_str = f"  {change:+.2f}%" if change is not None else ""
                lines.append(f"  {coin:<10}  {amount:>12}  x ${price:>12,.2f}  = ${value:>14,.2f}{change_str}")

        lines.append(f"\n  {'TOTAL':<10}  {'':>12}     {'':>14}    ${total:>14,.2f}")
        return "\n".join(lines)

    return "Unknown action."


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
