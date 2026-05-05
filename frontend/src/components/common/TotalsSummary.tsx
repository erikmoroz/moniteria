import { ArrowRight } from 'lucide-react'
import type { TransactionTotalItem, PlannedTransactionTotalItem, CurrencyExchangeTotalItem } from '../../types'

// ============= Props =============

interface TransactionProps {
  mode: 'transactions'
  totals: TransactionTotalItem[]
}

interface PlannedProps {
  mode: 'planned'
  totals: PlannedTransactionTotalItem[]
}

interface ExchangeProps {
  mode: 'exchanges'
  totals: CurrencyExchangeTotalItem[]
}

type Props = TransactionProps | PlannedProps | ExchangeProps

// ============= Helpers =============

function formatAmount(total: string): string {
  const num = parseFloat(total)
  return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// ============= Sub-renderers =============

function TransactionTotals({ totals }: { totals: TransactionTotalItem[] }) {
  return (
    <>
      {totals.map((item) => (
        <div key={`${item.type}-${item.currency}`} className="flex items-center gap-2">
          <span
            className={`inline-block w-2 h-2 rounded-full ${
              item.type === 'income' ? 'bg-positive' : 'bg-negative'
            }`}
          />
          <span className="text-text-muted text-xs font-sans capitalize">{item.type}</span>
          <span className="font-mono text-sm text-text">
            {formatAmount(item.total)} {item.currency}
          </span>
        </div>
      ))}
    </>
  )
}

function PlannedTotals({ totals }: { totals: PlannedTransactionTotalItem[] }) {
  return (
    <>
      {totals.map((item) => (
        <div key={item.currency} className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-primary" />
          <span className="font-mono text-sm text-text">
            {formatAmount(item.total)} {item.currency}
          </span>
        </div>
      ))}
    </>
  )
}

function ExchangeTotals({ totals }: { totals: CurrencyExchangeTotalItem[] }) {
  return (
    <>
      {totals.map((item) => (
        <div key={`${item.from_currency}-${item.to_currency}`} className="flex items-center gap-2">
          <span className="font-mono text-sm text-text">
            {formatAmount(item.from_total)} {item.from_currency}
          </span>
          <ArrowRight size={14} className="text-text-muted flex-shrink-0" />
          <span className="font-mono text-sm text-text">
            {formatAmount(item.to_total)} {item.to_currency}
          </span>
        </div>
      ))}
    </>
  )
}

// ============= Component =============

export default function TotalsSummary(props: Props) {
  if (props.totals.length === 0) return null

  return (
    <div className="bg-surface border border-border rounded-sm px-4 py-3 mt-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {props.mode === 'transactions' && <TransactionTotals totals={props.totals} />}
        {props.mode === 'planned' && <PlannedTotals totals={props.totals} />}
        {props.mode === 'exchanges' && <ExchangeTotals totals={props.totals} />}
      </div>
    </div>
  )
}
