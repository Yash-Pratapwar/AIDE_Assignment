SELECT
    feed,
    partition_name,
    string_agg(DISTINCT issue_type, ', ' ORDER BY issue_type) AS issue_types,
    max(expected_rows) AS expected_rows,
    max(actual_rows) AS actual_rows,
    max(expected_files) AS expected_files,
    max(actual_files) AS actual_files,
    string_agg(DISTINCT detail, '; ' ORDER BY detail)
        FILTER (WHERE detail IS NOT NULL) AS issue_details
FROM manifest_partition_issues
GROUP BY feed, partition_name
ORDER BY feed, partition_name
