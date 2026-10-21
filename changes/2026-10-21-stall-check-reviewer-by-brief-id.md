# Patch

#### Fixed

- **The stall check knows a reviewer by its `review-` brief ID again, not by `Hidden: yes`.** A reviewer that stays visible in the inbox no longer gets a "stuck: Your move" line as the author of the PR it reviews. `Hidden: yes` still decides only which lemons the inbox's default list leaves out.
