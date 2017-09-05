import os
import time
import sqlite3

from logger import log


class Allowed(object):
    def __init__(self, dbfile):
        first_used = not os.path.isfile(dbfile)
        self.db = sqlite3.connect(dbfile)
        self.updating = False
        if first_used:
            self.create_db()

    def create_db(self):
        self.db.execute("CREATE TABLE allowed_list (expiration int, ip text, description text)")
        self.db.commit()

    def get_allowed(self):
        cur = self.db.cursor()
        cur.execute("SELECT expiration, ip, description, ROWID FROM allowed_list")
        now = int(time.time())
        allowed = []
        to_remove = []
        for r in cur.fetchall():
            if r[0] == 0 or r[0] > now:
                allowed.append({
                    "ip": r[1],
                    "expiration": r[0],
                    "desc": r[2],
                    "id": r[3]
                })
            else:
                to_remove.append({
                    "ip": r[1],
                    "expiration": r[0],
                    "desc": r[2],
                    "id": r[3]
                })
        if len(to_remove) > 0 and not self.updating:
            for line in to_remove:
                log("Removing {}".format(line['ip']))
                self.db.execute(
                    "DELETE FROM allowed_list WHERE ip=? AND expiration=?",
                    (line['ip'], line['expiration'])
                )
            self.db.commit()
            self.update_conf(allowed)
        return allowed

    def add_allowed(self, ip, desc, expiration):
        log("Adding {}".format(ip))
        self.db.execute("INSERT INTO allowed_list (expiration, ip, description) VALUES (?, ?, ?)", (expiration, ip, desc))
        self.db.commit()
        self.update_conf()

    def del_allowed(self, allowed_id):
        log("Deleting id {}".format(allowed_id))
        self.db.execute("DELETE FROM allowed_list WHERE ROWID = ?", (allowed_id,))
        self.db.commit()
        self.update_conf()

    def update_conf(self, allowed=None):
        self.updating = True
        if allowed is None:
            allowed = self.get_allowed()
        with open("data/allow.conf", "w") as f:
            for line in allowed:
                f.write("allow {}; # {} - {} - {}\n".format(line['ip'], line['id'], line['expiration'], line['desc']))
        self.updating = False
