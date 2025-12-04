# ⚡ БЫСТРАЯ СПРАВКА: ПРАВИЛЬНЫЕ ЗАПРОСЫ

**Дата:** 2025-12-04  
**Статус:** ✅ ПРОТЕСТИРОВАНО

---

## 🔑 ГЛАВНОЕ ИЗМЕНЕНИЕ

### ❌ Было (неправильно):
```sql
COUNT(*) AS CUPS_COUNT  -- Считает заказы
```

### ✅ Стало (правильно):
```sql
SUM(GD.Source) AS CUPS_COUNT  -- Считает товары
```

---

## 📋 ТРИ ЗАПРОСА

### 1. Чашки (с JOIN)
```sql
SELECT 
    stgp.NAME AS STORE_NAME,
    D.DAT_ AS ORDER_DATE,
    SUM(CASE WHEN G.OWNER IN ('24435','25539','21671','25546','25775','25777','25789') 
        THEN GD.Source ELSE NULL END) AS MonoCup,
    SUM(CASE WHEN G.OWNER IN ('23076','21882','25767','248882','25788') 
        THEN GD.Source ELSE NULL END) AS BlendCup,
    SUM(CASE WHEN G.OWNER IN ('24491','21385') 
        THEN GD.Source ELSE NULL END) AS CaotinaCup,
    SUM(CASE WHEN G.OWNER IN ('24435','25539','21671','25546','25775','25777','25789',
                              '23076','21882','25767','248882','25788',
                              '24491','21385') 
        THEN GD.Source ELSE NULL END) AS AllCup
FROM STORZAKAZDT D
JOIN STORZDTGDS GD ON D.ID = GD.SZID
JOIN GOODS G ON GD.GODSId = G.ID
JOIN STORGRP stgp ON D.STORGRPID = stgp.ID
WHERE D.STORGRPID IN (?, ?, ?, ?, ?)
  AND D.CSDTKTHBID IN ('1', '2', '3', '5')
  AND D.DAT_ >= ? AND D.DAT_ <= ?
  AND NOT (D.comment LIKE '%мы;%' OR D.comment LIKE '%Мы;%' OR D.comment LIKE '%Тестирование%')
GROUP BY stgp.NAME, D.DAT_
```

### 2. Суммы (БЕЗ JOIN)
```sql
SELECT
    stgp.NAME AS STORE_NAME,
    D.DAT_ AS ORDER_DATE,
    SUM(D.SUMMA) AS TOTAL_CASH
FROM STORZAKAZDT D
JOIN STORGRP stgp ON D.STORGRPID = stgp.ID
WHERE D.STORGRPID IN (?, ?, ?, ?, ?)
  AND D.CSDTKTHBID IN ('1', '2', '3', '5')
  AND D.DAT_ >= ? AND D.DAT_ <= ?
  AND NOT (D.comment LIKE '%мы;%' OR D.comment LIKE '%Мы;%' OR D.comment LIKE '%Тестирование%')
GROUP BY stgp.NAME, D.DAT_
```

### 3. Килограммы (фильтр по ID групп)
```sql
SELECT
    stgp.NAME AS STORE_NAME,
    D.DAT_ AS ORDER_DATE,
    SUM(GD.SOURCE) AS PACKAGES_KG
FROM STORZAKAZDT D
JOIN STORZDTGDS GD ON D.ID = GD.SZID
JOIN GOODS G ON GD.GODSId = G.ID
JOIN STORGRP stgp ON D.STORGRPID = stgp.ID
WHERE D.STORGRPID IN (?, ?, ?, ?, ?)
  AND D.CSDTKTHBID IN ('1', '2', '3', '5')
  AND D.DAT_ >= ? AND D.DAT_ <= ?
  AND G.OWNER IN ('11077', '16279', '16276')  -- БЕЗ Caotina!
GROUP BY stgp.NAME, D.DAT_
```

---

## 🎯 ID ГРУПП

**Чашки:**
- Mono: `24435, 25539, 21671, 25546, 25775, 25777, 25789`
- Blend: `23076, 21882, 25767, 248882, 25788`
- Caotina: `24491, 21385`

**Килограммы:**
- Blend: `11077, 16279`
- Mono: `16276`
- ❌ Caotina: `22939` - **НЕ включать!**

---

## ⚠️ ВАЖНО

1. **Раздельные запросы** - не объединяйте в один
2. **SUM(GD.Source)** - не COUNT(*)
3. **Суммы БЕЗ JOIN** - чтобы избежать дублирования
4. **Фильтр по ID групп** для килограммов (не по названиям)
5. **БЕЗ Caotina** в килограммах

---

## 📊 ОТВЕТ API

```json
{
  "STORE_NAME": "BatumiMall",
  "ORDER_DATE": "2025-12-02T00:00:00",
  "MonoCup": 10.0,
  "BlendCup": 39.0,
  "CaotinaCup": 6.0,
  "ALLCUP": 55.0,
  "TOTAL_CASH": 608.55,
  "PACKAGES_KG": 0.25
}
```
