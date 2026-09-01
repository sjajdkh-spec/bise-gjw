# BISE Gujranwala Discord Result Bot

Python + discord.py + MongoDB bot for monitoring configured BISE Gujranwala roll numbers.

## Important limitation

The public BISE Gujranwala result page currently presents a CAPTCHA. This project **does not bypass CAPTCHA or other security controls**. The official-site adapter detects CAPTCHA and reports it cleanly.

If BISE provides a public, non-CAPTCHA result endpoint on result day, set `OFFICIAL_RESULT_URL` to that endpoint and adjust `result_provider.py` field mappings if needed.

## Commands

- `!addrole <roll> <9th|10th|11th|12th> <year>`
- `!removerole <roll>`
- `!roles`
- `!cmd` (alias of roles)
- `!checkresult <roll> <class> <year>`
- `!checkall`
- `!testrole <roll>`
- `!setchannel`
- `!help`

All administrative commands require Discord Administrator permission.

## Discord setup

Enable the **Message Content Intent** in the Discord Developer Portal.

Create:
- one result channel
- one role to mention for announcements

Put their IDs in Railway variables:
`RESULT_CHANNEL_ID`
`MENTION_ROLE_ID`

## MongoDB

Create a MongoDB database and put its connection string in:
`MONGODB_URI`

The watchlist and announced state survive Railway restarts.

## Railway

1. Upload this project to GitHub.
2. Create a Railway service from the GitHub repo.
3. Add all variables from `.env.example`.
4. Deploy.
5. Check logs for `Logged in as ...`.

## Testing before result day

Run:
`!testrole 123456`

This uses local test data and sends a realistic result embed. It does not contact BISE.

Then:
`!addrole 123456 9th 2026`

and:
`!roles`

## Result-day workflow

The checker polls configured, unannounced rolls. When a public official result response is available, it saves the result in MongoDB and announces it once in the configured result channel.

Do not set the polling interval to an aggressive value. The default loop is 60 seconds and requests are delayed between roll numbers.


## Updated 403 handling
The provider now handles 403, 429, 5xx, CAPTCHA/security pages, and an optional public fallback URL. It does not bypass access controls. It supports 9th/10th/11th/12th and 2026 input.
