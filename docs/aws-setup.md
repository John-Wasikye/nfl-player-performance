# Step 12: AWS account and guardrails

The first step of the AWS phase. No Terraform and no project code yet - this is console work plus two
installs, and it ends with an account that cannot quietly run up a bill.

Written 2026-10-01. Prices and console wording drift; if something here does not match what you see,
trust the console and correct this file.

## Before you open the browser

Gather:

- **An email address for the root account.** Use a dedicated one, not your everyday inbox - the root
  email is a permanent identity for the account and is painful to change later. A Gmail alias works:
  `john.wasikye+aws@gmail.com` delivers to your normal inbox but is a distinct address to AWS.
- **A payment card.** AWS requires one even when everything you do falls inside the free tier.
- **A phone number** for identity verification.
- **An MFA app or passkey** for the root user. An authenticator app on your phone is fine; AWS also
  supports passkeys now. You will set this up within minutes of the account existing.

Decide:

- **Region: `us-east-1` (N. Virginia).** Not a free choice - ACM certificates used by CloudFront must
  live in us-east-1, and CloudWatch billing metrics only publish there. Putting everything in one region
  avoids a split setup.
- **A globally unique bucket prefix.** S3 bucket names are unique across *all* AWS accounts on earth, so
  the logical names in `storage-design.md` (`nfl-raw`, `nfl-records`, `nfl-site`, `nfl-tfstate`) are
  almost certainly taken. Pick a prefix now and use it everywhere: `jw-nfl-` or `johnwasikye-nfl-`
  giving, for example, `jw-nfl-raw`. Write the choice down; Terraform will need it.

## 12.1 Create the account

1. Go to `aws.amazon.com` and choose **Create an AWS account**.
2. Enter the root email and an account name, then verify the email and set a root password.
3. Choose **Personal** for the account type and fill in the contact details.
4. Add the payment card. AWS may place a small temporary authorisation on it.
5. Complete phone/SMS identity verification.
6. **Choose the Basic support plan - it is free.** The Developer plan is $29/month and you do not need
   it. This is the one screen in signup where it is easy to spend money by accident.
7. Sign in to the console.

## 12.2 Lock the root user down immediately

The root user can do anything, including closing the account, and cannot be restricted by permissions.
Treat it as a break-glass credential.

1. **Enable MFA on root.** Top-right account menu -> **Security credentials** -> Multi-factor
   authentication -> assign an authenticator app or passkey.
2. **Do not create root access keys.** If any exist, delete them. A leaked root key is an unrecoverable
   situation.
3. **Stop using root** after this step. You will only need it again for a handful of things - closing the
   account, changing the support plan, a few billing settings.

## 12.3 Turn on IAM access to billing

Account menu -> **Account** -> **IAM user and role access to Billing Information** -> **Edit** ->
activate.

Do this before the next step. Without it, the admin identity you are about to create cannot see billing
data or create a budget, and the failure looks like a confusing permissions error rather than a setting
you missed.

## 12.4 Set the money guardrails before building anything

Two overlapping alerts, because they fail differently: a budget watches forecast cost and is easy to
read, an alarm watches the actual metric and fires through SNS.

**A budget.** Billing and Cost Management -> **Budgets** -> create a **cost budget**, monthly, **$5**.
Add alert thresholds at 50%, 80% and 100% of actual, plus one on *forecasted* cost, all emailed to you.
Two budgets are free.

**A billing alarm.** CloudWatch -> Alarms -> create alarm -> metric **Billing -> Total Estimated
Charges (`EstimatedCharges`)**, threshold **$5**. Create an SNS topic with your email as the subscriber.

- **The alarm must be created in us-east-1.** Billing metrics are only published there; in any other
  region the metric simply will not appear and you will think it is broken.
- **Open the confirmation email from SNS and click the link.** An unconfirmed subscription silently
  delivers nothing, which means an alarm that looks configured and tells you nothing. The same trap
  applies later to the pipeline failure and staleness alarms in step 15.

The first ten CloudWatch alarms are free, so these cost nothing.

## 12.5 Create an identity for daily use

One decision left here, and it is worth understanding rather than guessing.

**Option A - IAM Identity Center (recommended).** You sign in with `aws sso login` and the CLI receives
short-lived credentials that expire. Nothing long-lived is ever written to your laptop. Roughly ten
minutes more setup: enable Identity Center, create a user, create a permission set with
`AdministratorAccess`, assign it to the account, then `aws configure sso`.

**Option B - a plain IAM user.** Create a user, attach `AdministratorAccess`, enable MFA on it, create an
access key, then `aws configure`. Fewer concepts, but it puts a permanent key and secret in
`~/.aws/credentials` on your machine. Long-lived access keys sitting in a home directory are the single
most common way personal AWS accounts get taken over.

Either way: **MFA on the identity, and never reuse the root user for day-to-day work.** This choice does
not affect CI - step 18 uses GitHub Actions with OIDC, which stores no AWS keys regardless.

## 12.6 Install the tools

Neither is currently installed on this machine. Both are available through winget:

```
winget install Amazon.AWSCLI
winget install Hashicorp.Terraform
```

Open a new shell afterwards so the PATH updates, then check:

```
aws --version
terraform version
```

Terraform 1.10 and later locks remote state in S3 natively via `use_lockfile`, so **you do not need a
DynamoDB lock table** - most tutorials still tell you to create one. winget currently offers 1.16.x.

## 12.7 Connect the CLI

- Identity Center: `aws configure sso`, then `aws sso login`.
- IAM user: `aws configure` - access key, secret, region `us-east-1`, output `json`.

Verify with:

```
aws sts get-caller-identity
```

It should print your account id and the identity you just made. If it prints the root user, stop and fix
that before going further.

## Done when

- `aws sts get-caller-identity` returns your account and a non-root identity.
- Root has MFA enabled and no access keys.
- A $5 budget and a $5 billing alarm both exist, and you have clicked the SNS confirmation email.
- `terraform version` runs.
- You have written down your bucket prefix and confirmed the region is us-east-1.

## Two things to know for later

- **New accounts currently get up to $200 in credits over 6 months**, which will likely cover the early
  months of this project outright. The steady-state estimate is about $1-1.50/month (BUILD_PLAN.md
  section 13).
- **The CloudFront flat-rate Free plan lists accounts "using AWS Free Tier" as ineligible.** That may
  conflict with those credits. It does not matter yet - step 17 is where it lands - and the fallback is
  harmless, because pay-as-you-go CloudFront still includes 1 TB of transfer and 10M requests a month
  free. Check eligibility when you get there rather than now.

Next: step 13, the Terraform base (remote state, buckets, IAM roles, ECR, budget). The bucket layout is
already decided in `storage-design.md`.
