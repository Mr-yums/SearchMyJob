import json


class OpportunitiesRepository:
    def __init__(self, db, configuration):
        self.db = db
        self.configuration = configuration

    def rows(self, sql, args=()):
        return [dict(row) for row in self.db.execute(sql, args)]

    def offers(self):
        from searchmyjob.domain.search_quality import checks

        rows = [
            {**json.loads(x["data"]), **{k: v for k, v in x.items() if k != "data"}}
            for x in self.rows("SELECT * FROM offers ORDER BY found DESC LIMIT 500")
        ]
        pages = {
            r["offer_id"]: dict(r)
            for r in self.db.execute(
                "SELECT offer_id,created,contacts,application_mode FROM offer_pages"
            )
        }
        return [
            {
                **row,
                **checks(row, self.configuration.get("criteria")),
                "page_collected_at": pages.get(row["id"], {}).get("created"),
                "contact_candidates": json.loads(pages.get(row["id"], {}).get("contacts", "[]")),
                "application_mode": pages.get(row["id"], {}).get("application_mode", "not_checked"),
            }
            for row in rows
        ]

    def dossier_row(self, offer_id):
        return [
            dict(row)
            for row in self.db.execute("SELECT data,status FROM offers WHERE id=?", (offer_id,))
        ]

    def add_if_missing(self, offer_id, data, found, updated):
        return self.db.execute(
            "INSERT INTO offers(id,data,found,updated) VALUES (?,?,?,?)\n              ON CONFLICT(id) DO NOTHING",
            (
                offer_id,
                data,
                found,
                updated,
            ),
        )

    def upsert(self, offer_id, data, found, updated):
        return self.db.execute(
            "INSERT INTO offers(id,data,found,updated) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,updated=excluded.updated",
            (
                offer_id,
                data,
                found,
                updated,
            ),
        )

    def exists(self, offer_id):
        return self.db.execute("SELECT 1 FROM offers WHERE id=?", (offer_id,)).fetchone()

    def status(self, offer_id):
        return self.db.execute("SELECT status FROM offers WHERE id=?", (offer_id,)).fetchone()[0]

    def data_rows(self, offer_id):
        return [
            dict(row) for row in self.db.execute("SELECT data FROM offers WHERE id=?", (offer_id,))
        ]
