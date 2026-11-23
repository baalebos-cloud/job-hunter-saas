# Dedicated Slack support: owner checklist

Enterprise customers can ask for a shared Slack channel with the Baalebos support team
(Help & support → Dedicated Slack support). Requests arrive at `SUPPORT_EMAIL` with the
subject `[Priority] Slack channel request: <company>` and are listed in
**Owner console → Slack**.

The channels use **Slack Connect**, Slack's feature for channels shared between two
organisations. Baalebos does not create channels automatically: you create them in your
own Slack workspace, then record what you did in the Owner console so the customer is
told.

## One-time setup

1. **Create the Baalebos Slack workspace** (for example `baalebos.slack.com`) with the
   support address as the owner.
2. **Put the workspace on a paid Slack plan (Pro or higher).** According to Slack's help
   centre, each organisation in a Slack Connect channel must be on a paid plan. Check
   current plans at <https://slack.com/pricing>.
3. Add the people who answer support to the workspace.
4. Optional: create a channel naming rule, for example `#<company>-baalebos`.

## For each request

1. Open **Owner console → Slack** and read the request: company, the customer's Slack
   (paid plan, free plan, or no Slack yet), and who to invite (up to 10 emails).
2. In Slack, **create a channel** for the customer, for example `#acme-baalebos`.
3. **Invite the customer's people** to the channel with Slack Connect, using the emails
   from the request. Slack's steps:
   <https://slack.com/help/articles/115004151203-Slack-Connect-guide--Work-with-external-organizations>
4. In the Owner console, enter the **channel name**, add an optional note for the
   customer, and choose **Mark invited**. The customer is emailed straight away and told
   to accept the invitation from Slack.
5. When the customer has joined, choose **Mark connected**.

### If the customer is on a free Slack plan, or has no Slack yet

According to Slack's help centre:

- An organisation on a free plan, or new to Slack, can accept a Slack Connect channel
  invitation by starting a **free 90-day trial** of Slack Pro. A workspace can use this
  trial **only once**.
- If the trial ends without an upgrade, the workspace returns to the free plan and its
  **Slack Connect channels are disconnected**.
- The free plan still allows **one-to-one direct messages** with people at other
  organisations through Slack Connect.

Tell the customer this when you invite them (use the note field). If the channel later
disconnects, offer a one-to-one Slack Connect DM or email support instead, and keep the
request at **Connected** or move it to **Closed**, whichever matches what is in place.

Slack's terms can change: check <https://slack.com/help/articles/115004151203> before
relying on the details above.

## When a customer leaves Enterprise

1. In Slack, remove the customer's organisation from the channel (or archive it).
2. In the Owner console, choose **Close**. The customer can ask again later if they
   return to Enterprise.

## What customers are told

- Requests are only possible on Enterprise. Team members see their team's channel; only
  the team owner (the subscriber) can request it.
- They get an email when you mark the request as invited, with the channel name and
  your note.
- Email and Help & support stay available, and requests from Enterprise accounts are
  tagged **Priority** and listed first in Owner console → Support.
