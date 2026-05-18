# Основные виды уязвимостей 

### 🚨 DML_NO_WHERE
**Что это:**  
Использование `UPDATE` или `DELETE` без `WHERE`.

**Почему опасно:**  
- Любая ошибка затрагивает всю таблицу.  
- Частая причина «стерли продакшен».

**Примеры:**
```sql
UPDATE credit_contract SET is_closed = 1;
DELETE FROM application_obj;
```

---

### ✴️ SELECT_STAR
**Что это:**  
Использование `SELECT *` вместо явного списка колонок.

**Почему опасно / вредно:**  
- Тянет лишние (в т.ч. чувствительные) данные.  
- Ломает контракт схемы и увеличивает нагрузку.

**Примеры:**
```sql
SELECT * FROM credit_contract;
SELECT * FROM sys_company WHERE status = 1;
```

---

### 📄 NO_PAGINATION
**Что это:**  
Запросы без пагинации (`LIMIT`, `OFFSET`, оконные функции).

**Почему опасно:**  
- Перегружают БД, сеть и приложение.  
- Могут использоваться для DoS.

**Примеры:**
```sql
SELECT id, name FROM dict_product;
SELECT id, credit_amount FROM credit_contract WHERE is_closed = 0;
```

---

### 🔐 DIRECT_SENSITIVE
**Что это:**  
Прямой доступ к чувствительным данным.

**Примеры чувствительных полей:**  
- Финансы: `credit_amount`, `limit_over`, `reserve_size`  
- Клиенты: `link_customer_id`, `sys_company`

**Почему опасно:**  
- Утекают в логи и дампы.  
- При уязвимостях сразу раскрываются «сырые» данные.

---

### 💉 SQL_INJ_CLASSIC
**Что это:**  
SQL-инъекция через конкатенацию пользовательского ввода.

**Почему опасно:**  
- Возможность выполнить произвольный SQL.  
- Полный контроль над данными.

**Примеры:**
```sql
"SELECT id FROM sys_employee WHERE name = '" || user_name || "';"
"SELECT id FROM credit_contract WHERE credit_contract_number = '" || contract_num || "';"
```

---

### 🧩 SQL_INJ_UNION
**Что это:**  
Инъекция через `UNION SELECT`.

**Почему опасно:**  
- Позволяет вытягивать данные из других таблиц.

**Примеры:**
```sql
... WHERE id = 1 UNION SELECT password_hash FROM users ...
... UNION SELECT credit_amount, reserve_size FROM credit_contract ...
```

---

### ⏱ SQL_INJ_TIME
**Что это:**  
Time-based инъекция (`pg_sleep`, `SLEEP`, `WAITFOR DELAY`).

**Почему опасно:**  
- Работает в «слепых» атаках.  
- Позволяет извлекать данные по времени ответа.

**Примеры:**
```sql
SELECT pg_sleep(5) WHERE 'admin' = '" || user_input || "';
SELECT CASE WHEN condition THEN pg_sleep(3) ELSE 0 END;
```

---

### ⚙️ PLPGSQL_UNSAFE
**Что это:**  
Небезопасный динамический SQL в процедурах (`EXECUTE`, `format`).

**Почему опасно:**  
- Те же SQL-инъекции, но с повышенными правами.  
- Сложнее обнаружить.

**Примеры:**
```sql
EXECUTE 'SELECT * FROM credit_contract WHERE id = ' || contract_id;
EXECUTE format('DELETE FROM %I WHERE id = %s', user_table, user_id);
```

---

### 🔑 PRIV_ESCALATE
**Что это:**  
Опасные операции с правами (`GRANT`, `ALTER ROLE`).

**Почему опасно:**  
- Ошибки → повышение привилегий.  
- Риск полного контроля над БД.

**Примеры:**
```sql
GRANT ALL PRIVILEGES ON DATABASE prod TO some_user;
ALTER ROLE report_user WITH SUPERUSER;
```