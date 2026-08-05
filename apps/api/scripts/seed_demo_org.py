"""Seed a demo institution: one university, real people, four courses."""
import sys, uuid; sys.path.insert(0, '.')
from src.database import get_db_connection, get_cursor
from src.auth import DEV_USER_ID, DEV_WORKSPACE_ID, DEV_TENANT_ID

ORG = DEV_TENANT_ID          # the dev user's tenant IS the demo university
ADMIN = DEV_USER_ID          # so the anonymous browser session lands inside it

PEOPLE = [
    (ADMIN,        'dr.okafor@northgate.ac.uk',   'Dr. Amara Okafor',   'org_admin'),
    (str(uuid.uuid4()), 'prof.lindqvist@northgate.ac.uk', 'Prof. Erik Lindqvist', 'professor'),
    (str(uuid.uuid4()), 'dr.vasquez@northgate.ac.uk',     'Dr. Elena Vasquez',    'professor'),
    (str(uuid.uuid4()), 'j.adeyemi@northgate.ac.uk',      'Joseph Adeyemi',       'ta'),
    (str(uuid.uuid4()), 'm.chen@northgate.ac.uk',         'Mei Chen',             'student'),
    (str(uuid.uuid4()), 's.patel@northgate.ac.uk',        'Sana Patel',           'student'),
    (str(uuid.uuid4()), 'l.moreau@northgate.ac.uk',       'Luc Moreau',           'student'),
    (str(uuid.uuid4()), 'k.tanaka@northgate.ac.uk',       'Kenji Tanaka',         'student'),
]

COURSES = [
    (DEV_WORKSPACE_ID, 'PSY-601 Research Methods',      'psy-601'),
    (str(uuid.uuid4()), 'BIO-712 Molecular Genetics',   'bio-712'),
    (str(uuid.uuid4()), 'CS-540 Machine Learning',      'cs-540'),
    (str(uuid.uuid4()), 'ECON-430 Applied Econometrics','econ-430'),
]

with get_db_connection() as conn:
    cur = get_cursor(conn)
    cur.execute("""INSERT INTO tenants (tenant_id, name, slug)
                   VALUES (%s,%s,%s) ON CONFLICT (tenant_id) DO UPDATE SET name=EXCLUDED.name""",
                (ORG, 'Northgate University', 'northgate'))
    for wid, name, slug in COURSES:
        cur.execute("""INSERT INTO workspaces (workspace_id, tenant_id, name, slug)
                       VALUES (%s,%s,%s,%s) ON CONFLICT (workspace_id) DO UPDATE SET name=EXCLUDED.name""",
                    (wid, ORG, name, slug))
    cur.execute("""INSERT INTO organization_seats (org_id, seats_purchased, plan)
                   VALUES (%s,%s,%s) ON CONFLICT (org_id) DO UPDATE SET seats_purchased=EXCLUDED.seats_purchased""",
                (ORG, 25, 'institution'))
    for uid, email, name, role in PEOPLE:
        cur.execute("""INSERT INTO organization_members (org_id, user_id, email, display_name, org_role)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (org_id, user_id) DO UPDATE SET org_role=EXCLUDED.org_role""",
                    (ORG, uid, email, name, role))
        # everyone sees the flagship course; staff see all four
        targets = [c[0] for c in COURSES] if role in ('org_admin','professor','ta') else [COURSES[0][0]]
        for wid in targets:
            wrole = 'owner' if role == 'org_admin' else role  # professor / ta / student
            cur.execute("""INSERT INTO user_workspaces (user_id, workspace_id, role)
                           VALUES (%s,%s,%s) ON CONFLICT (user_id, workspace_id) DO UPDATE SET role=EXCLUDED.role""",
                        (uid, wid, wrole))
    conn.commit()

    cur.execute("SELECT name FROM tenants WHERE tenant_id=%s", (ORG,))
    print("  organisation:", cur.fetchone()['name'])
    cur.execute("SELECT count(*) n FROM workspaces WHERE tenant_id=%s", (ORG,))
    print("  courses:", cur.fetchone()['n'])
    cur.execute("SELECT org_role, count(*) n FROM organization_members WHERE org_id=%s GROUP BY 1 ORDER BY 1", (ORG,))
    print("  members:", {r['org_role']: r['n'] for r in cur.fetchall()})
    cur.execute("""SELECT s.seats_purchased,
                          (SELECT count(*) FROM organization_members
                            WHERE org_id=%s AND org_role='student') used
                   FROM organization_seats s WHERE s.org_id=%s""", (ORG, ORG))
    r=cur.fetchone(); print(f"  seats: {r['used']} students / {r['seats_purchased']} purchased")
