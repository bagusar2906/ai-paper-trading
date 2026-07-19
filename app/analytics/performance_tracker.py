from app.analytics.statistics import TradingStatistics


class PerformanceTracker:

    def calculate(self, trades):

        stats = TradingStatistics()

        if not trades:
            return stats

        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl < 0]
        breakeven = [t.pnl for t in trades if t.pnl == 0]

        stats.total_trades = len(trades)
        stats.winning_trades = len(wins)
        stats.losing_trades = len(losses)
        stats.breakeven_trades = len(breakeven)

        stats.gross_profit = sum(wins)
        stats.gross_loss = abs(sum(losses))

        stats.net_profit = (
            stats.gross_profit
            - stats.gross_loss
        )

        if stats.total_trades:

            stats.win_rate = (
                stats.winning_trades
                / stats.total_trades
            ) * 100

        if stats.gross_loss > 0:

            stats.profit_factor = (
                stats.gross_profit
                / stats.gross_loss
            )

        else:

            stats.profit_factor = float("inf")

        if wins:

            stats.average_win = (
                stats.gross_profit
                / len(wins)
            )

            stats.largest_win = max(wins)

        if losses:

            stats.average_loss = (
                sum(losses)
                / len(losses)
            )

            stats.largest_loss = min(losses)

        return stats