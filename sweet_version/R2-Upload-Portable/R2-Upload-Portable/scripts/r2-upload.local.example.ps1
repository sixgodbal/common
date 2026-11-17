$R2AccountId = "your-account-id"
$R2Bucket = "sweetman"
$R2AccessKeyId = "your-access-key-id"
$R2SecretAccessKey = "your-secret-access-key"
$R2PublicBaseUrl = "https://download.supercrazy.site"

# Default R2 key prefix for general dragged files
$R2DefaultPrefix = "guotang-star"

# Local source/output path and remote R2 key for LauncherManifest.xml
$LauncherManifestSourcePath = Join-Path ([Environment]::GetFolderPath("Desktop")) "LauncherManifest.xml"
$LauncherManifestRemoteKey = "launcher/LauncherManifest.xml"
