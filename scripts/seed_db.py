"""Seed the dockerized postgres with discriminative synthetic data.

Sizing rationale:
- Largest LIMIT in `data/dataset/tasks.jsonl` is 100. To make `LIMIT N` vs
  `LIMIT M` produce distinct result sets, the underlying filtered set must
  exceed both Ns. So we put 100+ rows behind every gold-relevant predicate.
- For NULL-vs-NOT-NULL splits, populated fraction is 50–80% to give a clear
  difference between "WHERE x IS NOT NULL" and a missing filter.
- For status/is_system/ord boolean-ish splits, the "true" side gets enough
  rows that any LIMIT in the gold fits inside it.

`sys_employee` and `sys_company` have many NOT NULL columns inherited from
the GreenData base type; we populate them with cycling values so that
result sets are deterministic, but the variation only matters on the columns
the gold queries actually touch.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

import psycopg
from mimesis import Finance, Generic, Person
from mimesis.locales import Locale

DEFAULT_DSN = "postgresql://case3:case3@localhost:55432/demo_db"

N_EMPLOYEES = 150
N_COMPANIES = 150
N_ACCOUNTS = 150
N_APP_OBJ = 60
N_DICT_ROWS = 30

# Explicit prefix-rich company names so ILIKE queries on sys_company.name
# (e.g. '%ООО%', 'АО %', '%Газ%', '%Строй%', '%Торг%', '%Инвест%',
# '%ООО Ромашка%', 'ИП Иванов Иван Иванович') match real rows.
_COMPANY_FIXED_NAMES: list[str] = [
    "ООО Ромашка",
    "ООО Газпром-Сервис",
    "ООО Стройтрест",
    "ООО Торг-Инвест",
    "ИП Иванов Иван Иванович",
    "АО Газпром",
    "АО Строй-Холдинг",
    "АО Инвест-Капитал",
    "АО Торговый Дом",
    "ПАО Газпромнефть",
]

_SEED = 42
_person_ru = Person(locale=Locale.RU, seed=_SEED)
_person_en = Person(locale=Locale.EN, seed=_SEED)
_finance_ru = Finance(locale=Locale.RU, seed=_SEED)
_finance_en = Finance(locale=Locale.EN, seed=_SEED)
_generic_ru = Generic(locale=Locale.RU, seed=_SEED)


def _employee_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_EMPLOYEES + 1):
        name = _person_en.full_name()
        name_ru = _person_ru.full_name() if i <= 80 else None
        type_id = ((i - 1) % 5) + 1
        org_id = ((i - 1) % 10) + 1  # 10 distinct groups for GROUP BY org_id
        status = 1 if i <= 100 else 0
        create_date = (
            datetime(2018, 1, 1) + timedelta(days=i)
            if i <= 60
            else datetime(2021, 6, 15) + timedelta(days=i)
        )
        user_id = ((i - 1) % 50) + 1
        emp_org_id = i
        created_emp_id = ((i - 1) % 30) + 1
        last_modified_user_id = ((i - 1) % 30) + 1
        last_modified_emp_id = ((i - 1) % 30) + 1
        last_modified_date = datetime(2024, 1, 1) + timedelta(hours=i)
        rows.append(
            (
                i,
                name,
                name_ru,
                type_id,
                org_id,
                status,
                create_date,
                user_id,
                emp_org_id,
                created_emp_id,
                last_modified_user_id,
                last_modified_emp_id,
                last_modified_date,
            )
        )
    return rows


def _company_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_COMPANIES + 1):
        # First slots get fixed prefix-rich names so ILIKE queries match.
        if i <= len(_COMPANY_FIXED_NAMES):
            name = _COMPANY_FIXED_NAMES[i - 1]
        else:
            name = _finance_en.company()
        name_ru = _finance_ru.company() if i <= 80 else None
        type_id = ((i - 1) % 20) + 1  # 20 distinct type_ids for DISTINCT queries
        org_id = ((i - 1) % 10) + 1
        status = 1 if i <= 100 else 0
        create_date = datetime(2019, 1, 1) + timedelta(days=i)
        user_id = ((i - 1) % 50) + 1
        created_emp_id = ((i - 1) % 30) + 1
        last_modified_user_id = ((i - 1) % 30) + 1
        last_modified_emp_id = ((i - 1) % 30) + 1
        last_modified_date = datetime(2024, 1, 1) + timedelta(hours=i)
        rows.append(
            (
                i,
                name,
                name_ru,
                type_id,
                org_id,
                status,
                create_date,
                user_id,
                created_emp_id,
                last_modified_user_id,
                last_modified_emp_id,
                last_modified_date,
            )
        )
    return rows


def _account_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_ACCOUNTS + 1):
        name = f"Account {_generic_ru.numeric.integer_number(start=10**6, end=10**8)}"
        name_ru = (
            f"Счёт №{_generic_ru.numeric.integer_number(start=10**6, end=10**8)}"
            if i <= 80
            else None
        )
        name_en = (
            f"Account #{_generic_ru.numeric.integer_number(start=10**6, end=10**8)}"
            if i <= 50
            else None
        )
        status = 1 if i <= 100 else 0
        is_system = 1 if i <= 30 else 0
        ord_v = i if i <= 100 else 0
        # parent_acc → existing rows. Reference ids 1..5; only set on rows
        # 6..50 so the FK target always exists when the row is inserted.
        parent_acc = ((i - 1) % 5) + 1 if 6 <= i <= 50 else None
        account_name = _finance_ru.company() if status == 1 else None
        last_modified_date = datetime(2024, 1, 1) + timedelta(hours=i)
        created_emp_id = ((i - 1) % 30) + 1 if i <= 80 else None
        rows.append(
            (
                i,
                name,
                name_ru,
                name_en,
                status,
                is_system,
                ord_v,
                parent_acc,
                account_name,
                last_modified_date,
                created_emp_id,
            )
        )
    return rows


# Common NOT NULL "base type" defaults — every GreenData object table inherits
# the same set of audit columns (type_id, org_id, user_id, created_emp_id, …).
_BASE_TYPE_ID = 1
_BASE_ORG_ID = 1
_BASE_USER_ID = 1
_BASE_EMP_ID = 1
_DEFAULT_CREATE = datetime(2020, 1, 1)
_DEFAULT_MODIFIED = datetime(2024, 1, 1)


def _sys_object_rows() -> list[tuple]:
    # Mirror sys_company id space so JOINs on initiator_id work.
    return [
        (
            i,
            f"Object {i}",
            _BASE_TYPE_ID,
            _BASE_ORG_ID,
            1,
            _DEFAULT_CREATE + timedelta(days=i),
            _BASE_USER_ID,
            _BASE_EMP_ID,
            _BASE_EMP_ID,
            _BASE_EMP_ID,
            _DEFAULT_MODIFIED + timedelta(hours=i),
        )
        for i in range(1, N_COMPANIES + 1)
    ]


def _sys_state_rows() -> list[tuple]:
    states = ["Создана", "На рассмотрении", "Одобрена", "Отклонена", "Закрыта"]
    return [
        (
            i,
            name,
            _DEFAULT_CREATE,
            _BASE_TYPE_ID,
            1,
            _BASE_ORG_ID,
            _BASE_USER_ID,
            f"STATE_{i}",
            i,
            _BASE_EMP_ID,
            _BASE_EMP_ID,
            _BASE_EMP_ID,
            _DEFAULT_MODIFIED,
        )
        for i, name in enumerate(states, start=1)
    ]


def _id_only_rows(n: int) -> list[tuple]:
    return [(i,) for i in range(1, n + 1)]


def _business_segment_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_DICT_ROWS + 21):  # 50 rows
        # First 20 have type_int_code; the rest are NULL so IS NOT NULL queries
        # discriminate. type_int_code cycles 1..6 so the "= 5" filter matches > 0 rows.
        type_int_code = ((i - 1) % 6) + 1 if i <= 20 else None
        rows.append(
            (
                i,
                f"Сегмент {i}",
                _DEFAULT_CREATE + timedelta(days=i),
                _BASE_TYPE_ID,
                1,
                _BASE_ORG_ID,
                _BASE_USER_ID,
                _DEFAULT_MODIFIED,
                _BASE_EMP_ID,
                _BASE_EMP_ID,
                _BASE_EMP_ID,
                f"BS_{i}",
                type_int_code,
            )
        )
    return rows


def _cb_interest_rate_rows() -> list[tuple]:
    rows = []
    for i in range(1, 51):
        date_start = _DEFAULT_CREATE + timedelta(days=i * 7) if i <= 35 else None
        date_end = _DEFAULT_CREATE + timedelta(days=i * 7 + 100) if i <= 30 else None
        grade = 5.0 + i * 0.25 if i <= 25 else None
        rows.append((i, f"Ставка ЦБ {i}", date_start, date_end, grade))
    return rows


def _type_loan_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_DICT_ROWS + 1):
        rows.append(
            (
                i,
                f"Тип кредита {i}",
                f"LOAN_{i}",
                1 if i <= 20 else 0,
                i if i <= 20 else None,
            )
        )
    return rows


def _dict_product_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_DICT_ROWS + 1):
        rows.append(
            (
                i,
                f"Кредитный продукт {i}",
                10_000_000 + i * 100_000,
                100_000 + i * 1_000,
                5.0 + (i % 10) * 0.5,
                12 + (i % 60),
            )
        )
    return rows


def _dict_div_presence_rows() -> list[tuple]:
    regions = [
        "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
        "Нижний Новгород", "Челябинск", "Самара", "Омск", "Ростов-на-Дону",
    ]
    return [(i, regions[(i - 1) % len(regions)]) for i in range(1, N_DICT_ROWS + 1)]


def _offices_psb_rows() -> list[tuple]:
    return [
        (i, f"Офис {i}", f"OFC_{i:03d}")
        for i in range(1, N_DICT_ROWS + 1)
    ]


def _scp_amd_product_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_DICT_ROWS + 1):
        rows.append(
            (
                i,
                1_000_000 + i * 50_000,
                12 + (i % 48),
            )
        )
    return rows


def _product_pricing_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_DICT_ROWS + 1):
        rows.append(
            (
                i,
                500_000 + i * 25_000,
                8.0 + (i % 10) * 0.25,
                10_000_000 + i * 100_000,
                ((i - 1) % N_DICT_ROWS) + 1,  # app_product_id → dict_product
                ((i - 1) % N_DICT_ROWS) + 1,  # type_loan_id → type_loan
                ((i - 1) % N_DICT_ROWS) + 1,  # amdp_parent_product_id → scp_amd_product
            )
        )
    return rows


def _application_obj_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_APP_OBJ + 1):
        # Last 10 rows get late dates so "WHERE create_date >= '2024-01-01'"
        # has non-empty result set.
        create_date = (
            _DEFAULT_CREATE + timedelta(days=i * 5)
            if i <= 50
            else datetime(2024, 1, 1) + timedelta(days=(i - 50) * 30)
        )
        rows.append(
            (
                i,
                f"Заявка {i}",
                create_date,
                ((i - 1) % N_COMPANIES) + 1,  # initiator_id
                ((i - 1) % N_EMPLOYEES) + 1,  # emp_id
                i if i <= 50 else None,  # processing_steps_id
                ((i - 1) % 20) + 1,  # scp_business_segment
                ((i - 1) % 20) + 1 if i <= 50 else None,  # industry_code_id
                i % 2,  # is_state_program
                i if i <= 40 else None,  # gsl_data_cont_id
                1,  # afp_state_id
            )
        )
    return rows


def _corp_tech_application_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_APP_OBJ + 1):
        # Last 10 rows get tiny lim_sum so "WHERE lim_sum <= {small}" matches.
        lim_sum = 1_000_000 + i * 10_000 if i <= 50 else i
        rows.append(
            (
                i,
                f"Тех. заявка {i}",
                _DEFAULT_CREATE + timedelta(days=i * 4),
                10_000_000 + i * 100_000 if i <= 50 else None,
                lim_sum,
                ((i - 1) % N_COMPANIES) + 1,  # initiator_id → sys_company
            )
        )
    return rows


def _ic_application_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_APP_OBJ + 1):
        rows.append(
            (
                i,
                f"IC заявка {i}",
                _DEFAULT_CREATE + timedelta(days=i * 3),
                ((i - 1) % N_DICT_ROWS) + 1 if i <= 50 else None,  # pricing_id
                i if i <= 40 else None,  # reason_refusal_id
                i % 2,  # is_state_program
            )
        )
    return rows


def _mler_application_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_APP_OBJ + 1):
        rows.append(
            (
                i,
                f"MLER заявка {i}",
                _DEFAULT_CREATE + timedelta(days=i * 4),
                f"Клиент {i}" if i <= 50 else None,  # mler_client_name
                _DEFAULT_MODIFIED + timedelta(days=i) if i <= 45 else None,
                500_000 + i * 10_000 if i <= 50 else i,  # lim_sum (small at tail)
                5_000_000 + i * 50_000 if i <= 45 else None,  # gsl_limit
                ((i - 1) % N_COMPANIES) + 1,  # initiator_id
            )
        )
    return rows


def _scp_application_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_APP_OBJ + 1):
        rows.append(
            (
                i,
                f"SCP заявка {i}",
                _DEFAULT_CREATE + timedelta(days=i * 3),
                1_000_000 + i * 25_000 if i <= 55 else i,  # lim_sum (small at tail)
                10_000_000 + i * 100_000 if i <= 50 else None,  # gsl_limit
                i % 2,  # is_state_program
                ((i - 1) % N_DICT_ROWS) + 1 if i <= 50 else None,  # pricing_id
                i if i <= 40 else None,  # reason_refusal_id
                ((i - 1) % N_COMPANIES) + 1,  # initiator_id
                ((i - 1) % 20) + 1,  # scp_business_segment
                ((i - 1) % N_DICT_ROWS) + 1,  # deleg_region_id
                ((i - 1) % N_DICT_ROWS) + 1,  # ca_rout_office_id
                1,  # afp_state_id
            )
        )
    return rows


def _scp_collateral_app_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_APP_OBJ + 1):
        rows.append(
            (
                i,
                ((i - 1) % N_APP_OBJ) + 1 if i <= 50 else None,  # app_obj_id
                f"Обеспечение {i}" if i <= 45 else None,
                100_000 + i * 5_000 if i <= 50 else None,  # attr_market_val
                80_000 + i * 4_000 if i <= 45 else None,  # attr_collateral_val
            )
        )
    return rows


def _scp_decision_quest_rows() -> list[tuple]:
    rows = []
    for i in range(1, N_APP_OBJ + 1):
        rows.append(
            (
                i,
                500_000 + i * 15_000 if i <= 50 else None,  # est_credit_limit
                ((i - 1) % N_DICT_ROWS) + 1 if i <= 45 else None,  # type_loan_id
            )
        )
    return rows


def seed(dsn: str = DEFAULT_DSN) -> None:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        # Drop everything in dependency order. CASCADE handles fan-out.
        cur.execute(
            """
            TRUNCATE
                public.sys_employee, public.sys_company, public.acc_number,
                public.sys_object, public.sys_state,
                public.scp_dict_tech_ctredit, public.scp_gov_program_dict,
                public.scp_techcred, public.scp_project_ans,
                public.business_segment, public.cb_interest_rate,
                public.type_loan, public.dict_product, public.dict_div_presence,
                public.offices_psb, public.scp_amd_product,
                public.product_pricing,
                public.application_obj, public.corp_tech_application,
                public.ic_application, public.mler_application,
                public.scp_application, public.scp_collateral_app,
                public.scp_decision_quest
            CASCADE;
            """
        )

        cur.executemany(
            """
            INSERT INTO public.sys_employee
                (id, name, name__ru, type_id, org_id, status, create_date, user_id,
                 emp_org_id, created_emp_id, last_modified_user_id,
                 last_modified_emp_id, last_modified_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            _employee_rows(),
        )
        cur.executemany(
            """
            INSERT INTO public.sys_company
                (id, name, name__ru, type_id, org_id, status, create_date, user_id,
                 created_emp_id, last_modified_user_id, last_modified_emp_id,
                 last_modified_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            _company_rows(),
        )
        cur.executemany(
            """
            INSERT INTO public.acc_number
                (id, name, name__ru, name__en, status, is_system, ord, parent_acc,
                 account_name, last_modified_date, created_emp_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            _account_rows(),
        )

        # System / supporting tables first — many app FKs target these.
        cur.executemany(
            """
            INSERT INTO public.sys_object
                (id, name, type_id, org_id, status, create_date, user_id,
                 created_emp_id, last_modified_user_id, last_modified_emp_id,
                 last_modified_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            _sys_object_rows(),
        )
        cur.executemany(
            """
            INSERT INTO public.sys_state
                (id, name, create_date, type_id, status, org_id, user_id,
                 afr_ident, afr_ord, created_emp_id, last_modified_user_id,
                 last_modified_emp_id, last_modified_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            _sys_state_rows(),
        )

        # ID-only dictionaries (every column except id is nullable).
        for table, n in (
            ("scp_dict_tech_ctredit", 5),
            ("scp_gov_program_dict", 5),
            ("scp_techcred", 5),
            ("scp_project_ans", 5),
        ):
            cur.executemany(
                f"INSERT INTO public.{table} (id) VALUES (%s);",
                _id_only_rows(n),
            )

        cur.executemany(
            """
            INSERT INTO public.business_segment
                (id, name, create_date, type_id, status, org_id, user_id,
                 last_modified_date, last_modified_user_id, created_emp_id,
                 last_modified_emp_id, ident, type_int_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            _business_segment_rows(),
        )
        cur.executemany(
            """
            INSERT INTO public.cb_interest_rate
                (id, name, date_start_cb, date_end_cb, grade_number_cb)
            VALUES (%s, %s, %s, %s, %s);
            """,
            _cb_interest_rate_rows(),
        )
        cur.executemany(
            "INSERT INTO public.type_loan (id, name, ident, status, ord) VALUES (%s, %s, %s, %s, %s);",
            _type_loan_rows(),
        )
        cur.executemany(
            """
            INSERT INTO public.dict_product
                (id, name, max_sum_credit, min_sum_credit, credit_interest_rate, loan_terms)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            _dict_product_rows(),
        )
        cur.executemany(
            "INSERT INTO public.dict_div_presence (id, nameregion) VALUES (%s, %s);",
            _dict_div_presence_rows(),
        )
        cur.executemany(
            "INSERT INTO public.offices_psb (id, office_name, office_code) VALUES (%s, %s, %s);",
            _offices_psb_rows(),
        )
        cur.executemany(
            "INSERT INTO public.scp_amd_product (id, scp_general_amount, product_term) VALUES (%s, %s, %s);",
            _scp_amd_product_rows(),
        )
        cur.executemany(
            """
            INSERT INTO public.product_pricing
                (id, cr_amount, scp_calc_rate_val, gsl_limit,
                 app_product_id, type_loan_id, amdp_parent_product_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """,
            _product_pricing_rows(),
        )

        # Application tables.
        cur.executemany(
            """
            INSERT INTO public.application_obj
                (id, name, create_date, initiator_id, emp_id, processing_steps_id,
                 scp_business_segment, industry_code_id, is_state_program,
                 gsl_data_cont_id, afp_state_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            _application_obj_rows(),
        )
        cur.executemany(
            """
            INSERT INTO public.corp_tech_application
                (id, name, create_date, gsl_limit, lim_sum, initiator_id)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            _corp_tech_application_rows(),
        )
        cur.executemany(
            """
            INSERT INTO public.ic_application
                (id, name, create_date, pricing_id, reason_refusal_id, is_state_program)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            _ic_application_rows(),
        )
        cur.executemany(
            """
            INSERT INTO public.mler_application
                (id, name, create_date, mler_client_name, date_amd_decision,
                 lim_sum, gsl_limit, initiator_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            _mler_application_rows(),
        )
        cur.executemany(
            """
            INSERT INTO public.scp_application
                (id, name, create_date, lim_sum, gsl_limit, is_state_program,
                 pricing_id, reason_refusal_id, initiator_id, scp_business_segment,
                 deleg_region_id, ca_rout_office_id, afp_state_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            _scp_application_rows(),
        )

        cur.executemany(
            """
            INSERT INTO public.scp_collateral_app
                (id, app_obj_id, collat_obj_name, attr_market_val, attr_collateral_val)
            VALUES (%s, %s, %s, %s, %s);
            """,
            _scp_collateral_app_rows(),
        )
        cur.executemany(
            "INSERT INTO public.scp_decision_quest (id, est_credit_limit, type_loan_id) VALUES (%s, %s, %s);",
            _scp_decision_quest_rows(),
        )

        conn.commit()

        cur.execute("SELECT count(*) FROM public.sys_employee;")
        n_emp = cur.fetchone()[0]  # type: ignore[index]
        cur.execute("SELECT count(*) FROM public.sys_company;")
        n_co = cur.fetchone()[0]  # type: ignore[index]
        cur.execute("SELECT count(*) FROM public.acc_number;")
        n_acc = cur.fetchone()[0]  # type: ignore[index]
        print(f"Seeded: sys_employee={n_emp}, sys_company={n_co}, acc_number={n_acc}")


if __name__ == "__main__":
    dsn = os.environ.get("EVAL_DATABASE_URL", DEFAULT_DSN)
    try:
        seed(dsn)
    except psycopg.OperationalError as e:
        print(f"Could not connect to postgres at {dsn}: {e}", file=sys.stderr)
        sys.exit(1)
