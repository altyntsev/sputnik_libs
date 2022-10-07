import alt_proc.cfg
import alt_proc.pg

def connect_db():

    alt_proc_cfg = alt_proc.cfg.read_global('sputnik')
    db = alt_proc.pg.DB(**alt_proc_cfg.db)

    return db