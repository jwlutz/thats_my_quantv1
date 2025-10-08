# Critical Fixes Needed for YFinanceProvider

## Remaining Bugs to Fix:

### 1. get_bar() - Returns Series instead of dict (line 135)
**Problem**: `row['Open']` returns a Series when index has duplicate dates
**Fix**: Convert to scalar values using `.item()` or access single value properly

```python
# Current (BROKEN):
return {
    'open': row['Open'],
    'high': row['High'],
    ...
}

# Should be:
return {
    'open': float(row['Open']),
    'high': float(row['High']),
    'low': float(row['Low']),
    'close': float(row['Close']),
    'volume': float(row['Volume'])
}
```

### 2. get_earnings_data() - Timezone comparison issue (line 171)
**Problem**: Comparing timezone-aware earnings index with timezone-naive as_of_datetime
**Fix**: Make as_of_datetime timezone-aware

```python
# Current (BROKEN):
as_of_datetime = pd.Timestamp(as_of_date)
past_earnings = earnings[earnings.index < as_of_datetime]

# Should be:
as_of_datetime = pd.Timestamp(as_of_date)
if earnings.index.tz is not None:
    as_of_datetime = as_of_datetime.tz_localize(earnings.index.tz)
past_earnings = earnings[earnings.index < as_of_datetime]
```

### 3. get_calendar() - Returns empty dict instead of None (line 302-304)
**Problem**: Empty dict {} fails "is None" check
**Fix**: Check if dict is empty

```python
# Current (BROKEN):
if calendar is None or (isinstance(calendar, pd.DataFrame) and calendar.empty):
    return None
return calendar

# Should be:
if calendar is None:
    return None
if isinstance(calendar, pd.DataFrame) and calendar.empty:
    return None
if isinstance(calendar, dict) and len(calendar) == 0:
    return None
return calendar
```

### 4. get_fast_info() - Returns object with wrong attributes (line 311-323)
**Problem**: __dict__ contains private attributes, not public ones
**Fix**: Iterate over public attributes or convert properly

```python
# Current (BROKEN):
if hasattr(fast_info, '__dict__'):
    return dict(fast_info.__dict__)

# Should be:
# Extract public attributes
result = {}
for attr in dir(fast_info):
    if not attr.startswith('_'):
        try:
            result[attr] = getattr(fast_info, attr)
        except:
            pass
if len(result) == 0:
    return None
return result
```

### 5. Test assertions need timezone-aware comparisons
Some tests compare timezone-naive and timezone-aware timestamps. Tests should use:
```python
# Instead of:
assert divs.index.min() >= pd.Timestamp(start)

# Use:
start_ts = pd.Timestamp(start).tz_localize(divs.index.tz) if divs.index.tz else pd.Timestamp(start)
assert divs.index.min() >= start_ts
```

## Summary
All 5 bugs are timezone/type conversion issues. The core logic is correct, just need proper type handling.
