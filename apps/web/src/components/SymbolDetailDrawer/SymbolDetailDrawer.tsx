import type { SignalRecord, SymbolHistoryResponse } from "../../types/dashboard";
import { EmptyState } from "../EmptyState/EmptyState";
import { XIcon } from "../Icons/Icons";
import { LoadingState } from "../LoadingState/LoadingState";
import {
  formatProbabilityTierLabel,
  formatQuadrantLabel,
  formatShiftStateLabel,
  formatSignalLabel,
} from "../../utils/dashboardLabels";


type SymbolDetailDrawerProps = {
  selectedSymbol: string;
  signal?: SignalRecord;
  history?: SymbolHistoryResponse;
  isLoading: boolean;
  error?: Error | null;
  onClose: () => void;
};


export function SymbolDetailDrawer(props: SymbolDetailDrawerProps) {
  if (!props.selectedSymbol) {
    return null;
  }

  return (
    <aside className="detail-drawer">
      <div className="detail-drawer__header">
        <div>
          <p className="eyebrow">标的详情</p>
          <h3>{props.selectedSymbol}</h3>
        </div>
        <button
          className="button button--ghost button--icon"
          type="button"
          onClick={props.onClose}
          aria-label="关闭标的详情"
          title="关闭标的详情"
        >
          <XIcon aria-hidden="true" />
        </button>
      </div>

      {props.isLoading ? (
        <LoadingState title="正在加载标的详情" note="正在拉取最新信号和历史轨迹。" />
      ) : null}

      {!props.isLoading && props.error ? (
        <EmptyState
          tone="error"
          title="标的详情加载失败"
          note={props.error.message}
        />
      ) : null}

      {!props.isLoading && !props.error && props.signal ? (
        <div className="detail-drawer__body">
          <div className="detail-drawer__badges">
            <span className="badge">{formatQuadrantLabel(props.signal.quadrant)}</span>
            <span className="badge badge--accent">{formatSignalLabel(props.signal.signal_label)}</span>
            <span className="badge">{formatProbabilityTierLabel(props.signal.prob_tier)}</span>
          </div>

          <dl className="detail-drawer__metrics">
            <div>
              <dt>S_dir</dt>
              <dd>{formatScore(props.signal.s_dir)}</dd>
            </div>
            <div>
              <dt>S_vol</dt>
              <dd>{formatScore(props.signal.s_vol)}</dd>
            </div>
            <div>
              <dt>S_conf</dt>
              <dd>{formatScore(props.signal.s_conf)}</dd>
            </div>
            <div>
              <dt>S_pers</dt>
              <dd>{formatScore(props.signal.s_pers)}</dd>
            </div>
          </dl>

          <section className="detail-drawer__history">
            <header>
              <h4>历史轨迹</h4>
              <span>{props.history?.lookback_days ?? 0} 天</span>
            </header>

            {props.history && props.history.items.length > 0 ? (
              <ul className="history-list">
                {[...props.history.items].reverse().map((item) => (
                  <li key={`${item.trade_date}-${item.batch_id}`} className="history-list__item">
                    <div>
                      <strong>{item.trade_date}</strong>
                      <span>{formatSignalLabel(item.signal_label)}</span>
                    </div>
                    <div className="history-list__meta">
                      <span>{formatShiftStateLabel(item.shift_state)}</span>
                      <span>{formatScore(item.s_conf)}/{formatScore(item.s_pers)}</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title="暂无历史记录"
                note="当前标的详情接口没有返回回看数据。"
              />
            )}
          </section>
        </div>
      ) : null}
    </aside>
  );
}


function formatScore(value: number | null): string {
  if (value === null) {
    return "暂无";
  }
  return value.toFixed(1);
}
