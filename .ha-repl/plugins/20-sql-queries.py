from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # For linters and type checkers only, and never run: what ha-repl itself
    # provides, declared in the `homeassistant-repl` library. They are used at
    # run time, which is the point, hence the noqa.

    from homeassistant_repl.plugin import MODE, sql  # noqa: TC004
    from homeassistant_repl.sql import SqlResult

# use the `sn_events.query` and similar for other queries will show the sql
# also allows you to do `sql(sn_events.query,raw=True).show()` to get a raw version, or change `max_rows`,`legacy` etc

if MODE != "api":
    # Retrieve most recently fired `supernotification` events with their payload

    sn_events: SqlResult = sql(  # type: ignore[assignment]
        """SELECT e.event_id, e.origin_idx, e.time_fired_ts, d.shared_data
                                            FROM events e
                                            INNER JOIN event_types t ON t.event_type_id = e.event_type_id
                                            INNER JOIN event_data d ON e.data_id = d.data_id
                                            WHERE t.event_type = 'supernotification'
                                            ORDER BY e.time_fired_ts DESC
                                            """,
        max_rows=10,
    )
    sn_stats: SqlResult = sql(  # type: ignore[assignment]
        """SELECT * FROM statistics_history
                                    WHERE statistic_id IN ("sensor.supernotify_failures","sensor.supernotify_notifications")"""
    )

    # WIP - will simplify joins and func calls upstream
    # from homeassistant.components.logbook.models import bytes_to_ulid_or_none
    # parent_events={bytes_to_ulid_or_none(r[1]):r[0] for r in sql("""select e.event_id,e.context_id_bin from events e WHERE e.context_id_bin IS NOT NULL""",max_rows=None)}
    # sn_events_with_parent_ctx_ids={r[0]:bytes_to_uuid_hex_or_none(r[1]) for r in sql("""select e.event_id,e.context_parent_id_bin from events e
    #                            WHERE t.event_type = 'supernotification' AND e.context_parent_id_bin IS NOT NULL"""
    #               ,max_rows=None)}
