use std::path::PathBuf;
use std::process::Command;
use sha2::{Sha256, Digest};
use aes_gcm::{Aes256Gcm, Key, Nonce};
use aes_gcm::aead::{Aead, KeyInit};
use rsa::{RsaPublicKey, RsaPrivateKey, pkcs1::DecodeRsaPublicKey, pkcs8::DecodePrivateKey};
use serde::{Serialize, Deserialize};
use tauri::Manager;
use winreg::RegKey;
use winreg::enums::*;

const RSA_PUBLIC_KEY_PEM: &str = "-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEArf7+GqMMUG3w5X09haVlkkcFxzWGBEhFFqSWRLRuPifZW4g9tH1Q
8BP/wwcPnr/WuHTpNLy8QP34dTO9Q56so3jrJ8A+gBGZ4EQGxmSHIF12m7QI350J
yzGt3x+N+ZvuhyqdjW38k0OFbdR3B4qAdoBTWIKZdOjpKahubP9Ye/TEYEYCNyHo
De4VXNAfce5hYCphwXq1Ie0smF/52qqZMBH+LgAWErmu0IDi12vGuWRVMkcfLhd6
Ced0BZTz5z6rdRY1bSm3L0Fvr21I6zfj+egwYHh1FlWZm/UbiLLiC8siaPpSnhwS
8+CpbEsSSKbZSJEgjxUGoLvwcGU2qz8srwIDAQAB
-----END RSA PUBLIC KEY-----";

const RSA_PRIVATE_KEY_PEM: &str = "-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCt/v4aowxQbfDl
fT2FpWWSRwXHNYYESEUWpJZEtG4+J9lbiD20fVDwE//DBw+ev9a4dOk0vLxA/fh1
M71DnqyjeOsnwD6AEZngRAbGZIcgXXabtAjfnQnLMa3fH435m+6HKp2NbfyTQ4Vt
1HcHioB2gFNYgpl06OkpqG5s/1h79MRgRgI3IegN7hVc0B9x7mFgKmHBerUh7SyY
X/naqpkwEf4uABYSua7QgOLXa8a5ZFUyRx8uF3oJ53QFlPPnPqt1FjVtKbcvQW+v
bUjrN+P56DBgeHUWVZmb9RuIsuILyyJo+lKeHBLz4KlsSxJIptlIkSCPFQagu/Bw
ZTarPyyvAgMBAAECggEASbkwAKhSSOf0eMBip3SHv32RYLF4ier3PxtYwl6zEWoA
Cm0FPCsW9sp6ha/BuhFt0PVUdLB9kYoq0ror+PFME+3hsZOex9PtX51jQ3+H07pW
Ta3wTpMy+aIgmlg752XfIO15GVpfeSRUbk9mac8RFGTWK7wWendPiAOiWlOtMcO2
7SEye2ygTtQUyGiKUHxtnMDTpOMWjguQjHlC6rLGrKXMNOFwhIHTXL24L+oGOgZ8
RW3ctI6BA50tqLDhnonOPXsL3Cu3O12zTEFjehCyO54MXt+rIy2Gxq7eydE8Leme
pintWpDomoAYA6bUGvILeag9AVmAR0yH1zjYDzl52QKBgQDV89Lo9hAZojh8sCYa
tS4XbJuPHRZoBgB3ygJvf6C3cw/HX6dt3Vs2CUTZ3TYIoYtUrMZIMB4NsaLX+E8V
ZJBMdD+YkMwjEYyl0dD/UvE+z6fpIcez7lXOCwtY8uzOwsJjjM8NWW4FQUugcCdT
q6SsIQIQtFy8SCvthtpRmhphdwKBgQDQMOu+O6u4qNZll3Y9+nPCqOSk6LBwAIdv
Dw6zLGge0e1PqLZyxBYgUz+fODAXB3ahuPVV4S+Q8+JgtbgNyDPxm2ccBH7Ytbhg
u1BVfhLglp05pJH0FqW61N2YhXJPkUbXD+a0GaEFUXr7Wiz5oZ8LWwNeS0oVmKHe
EN6UEUgciQKBgGnls0DnefSWHItqzJFvmA60DRL6/LokLlscO7RgYXYrl2XBbKeu
ZpUKZW/IVBRVkRcqJUJZvqZchBONrecSzXFqIIgtMz0wVINGpMGblhjWw29a7vOa
RhIj2Uv/gUKdl4Wajmk3GIO1W+9fU7fQP0OLWvBVtYjj2ApLMwgs1F3lAoGAMRYX
vzaaemN0iWd4vYw7lv3zSt6CGyZEyG6obJ5fvkSIy2tf+Rc6kEyQh53b2NItqlvN
nH4HlQmrqlmuF7HIbYLSgMyei8HswwHnIwEiuklIsLqYnxBn6vEdfkSYeyIprbNW
FcilKnfXo0PTrtfog+jllmnyAb2HDLC1ifu5IOECgYEAvQ5HCmAey4OBMNlOq/0X
g6m1uD6qQZkcQ32DyHhvNDHpzF6Lx40ILcuvfxki5KZNC/oJh+rYOoXuNf6G/Rmg
YbUgd2l1DqNPCsLKfM6tEMCKnZfJfelvfqhkpyI9FpmPXZEda9+9zfGE+hVq1R7c
MQZXwFS/3FGzAprVuqaHhEY=
-----END PRIVATE KEY-----";

const AES_KEY_BYTES: &[u8; 32] = b"ReportQA_OffLine_License_AESKey!"; 
const AES_NONCE_BYTES: &[u8; 12] = b"RQA_NonceGCM";

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct LicensePayload {
    pub license_id: String,
    pub product_id: String,
    pub customer_id: String,
    pub fingerprints: Vec<String>,
    pub edition: String,
    pub features: Vec<String>,
    pub issue_date: String,
    pub expire_date: String,
    pub permanent: bool,
    pub salt: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct LicenseInfo {
    pub is_activated: bool,
    pub is_expired: bool,
    pub license_id: String,
    pub edition: String,
    pub expire_date: String,
    pub permanent: bool,
    pub features: Vec<String>,
}

fn get_sha256_prefix(val: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(val.trim().as_bytes());
    let res = hasher.finalize();
    let hex_string: String = res.iter().map(|b| format!("{:02x}", b)).collect();
    hex_string[0..8].to_uppercase()
}

fn query_cmd(cmd: &str, args: &[&str]) -> String {
    Command::new(cmd)
        .args(args)
        .output()
        .map(|o| {
            let s = String::from_utf8_lossy(&o.stdout).to_string();
            s.lines()
                .skip(1)
                .map(|line| line.trim())
                .filter(|line| !line.is_empty())
                .collect::<Vec<_>>()
                .join(" ")
        })
        .unwrap_or_default()
}

pub fn collect_fingerprints() -> Vec<String> {
    let machine_guid = RegKey::predef(HKEY_LOCAL_MACHINE)
        .open_subkey("SOFTWARE\\Microsoft\\Cryptography")
        .and_then(|k| k.get_value::<String, _>("MachineGuid"))
        .unwrap_or_else(|_| "UNKNOWN_GUID".to_string());

    let cpu_id = query_cmd("wmic", &["cpu", "get", "processorid"]);
    let cpu_id = if cpu_id.is_empty() { "UNKNOWN_CPU".to_string() } else { cpu_id };

    let board_sn = query_cmd("wmic", &["baseboard", "get", "serialnumber"]);
    let board_sn = if board_sn.is_empty() { "UNKNOWN_BOARD".to_string() } else { board_sn };

    let disk_sn = query_cmd("wmic", &["diskdrive", "get", "serialnumber"]);
    let disk_sn = if disk_sn.is_empty() { "UNKNOWN_DISK".to_string() } else { disk_sn };

    vec![
        get_sha256_prefix(&machine_guid),
        get_sha256_prefix(&cpu_id),
        get_sha256_prefix(&board_sn),
        get_sha256_prefix(&disk_sn),
    ]
}

pub fn get_local_machine_code() -> String {
    collect_fingerprints().join("-")
}

fn get_appdata_path(app_handle: &tauri::AppHandle) -> Option<PathBuf> {
    app_handle.path().app_local_data_dir().ok().map(|p| p.join("license.dat"))
}

fn get_programdata_path() -> PathBuf {
    PathBuf::from("C:\\ProgramData\\report-qa\\license.dat")
}

fn encrypt_data(plain: &str) -> Option<Vec<u8>> {
    let key = Key::<Aes256Gcm>::from_slice(AES_KEY_BYTES);
    let cipher = Aes256Gcm::new(key);
    let nonce = Nonce::from_slice(AES_NONCE_BYTES);
    cipher.encrypt(nonce, plain.as_bytes()).ok()
}

fn decrypt_data(encrypted: &[u8]) -> Option<String> {
    let key = Key::<Aes256Gcm>::from_slice(AES_KEY_BYTES);
    let cipher = Aes256Gcm::new(key);
    let nonce = Nonce::from_slice(AES_NONCE_BYTES);
    cipher.decrypt(nonce, encrypted)
        .ok()
        .and_then(|bytes| String::from_utf8(bytes).ok())
}

fn read_registry() -> Option<String> {
    let k = RegKey::predef(HKEY_CURRENT_USER).open_subkey("Software\\ReportQA\\License").ok()?;
    let b64: String = k.get_value("LicenseData").ok()?;
    let enc = base64::Engine::decode(&base64::engine::general_purpose::STANDARD, &b64).ok()?;
    decrypt_data(&enc)
}

fn write_registry(plain: &str) {
    if let Some(enc) = encrypt_data(plain) {
        if let Ok((k, _)) = RegKey::predef(HKEY_CURRENT_USER).create_subkey("Software\\ReportQA\\License") {
            let b64 = base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &enc);
            let _ = k.set_value("LicenseData", &b64);
        }
    }
}

fn read_file(path: &PathBuf) -> Option<String> {
    std::fs::read(path).ok().and_then(|enc| decrypt_data(&enc))
}

fn write_file(path: &PathBuf, plain: &str) {
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    if let Some(enc) = encrypt_data(plain) {
        let _ = std::fs::write(path, enc);
    }
}

fn load_registration_code(app_handle: &tauri::AppHandle) -> Option<String> {
    let r1 = read_registry();
    let r2 = get_appdata_path(app_handle).and_then(|p| read_file(&p));
    let r3 = read_file(&get_programdata_path());

    let candidates = vec![r1, r2, r3];
    let mut votes = std::collections::HashMap::new();
    for c in candidates.into_iter().flatten() {
        *votes.entry(c).or_insert(0) += 1;
    }

    let winner = votes.into_iter().max_by_key(|&(_, count)| count).map(|(code, _)| code);

    if let Some(ref code) = winner {
        write_registry(code);
        if let Some(p) = get_appdata_path(app_handle) {
            write_file(&p, code);
        }
        write_file(&get_programdata_path(), code);
    }

    winner
}

pub fn save_registration_code(app_handle: &tauri::AppHandle, code: &str) {
    write_registry(code);
    if let Some(p) = get_appdata_path(app_handle) {
        write_file(&p, code);
    }
    write_file(&get_programdata_path(), code);
}

pub fn delete_registration_code(app_handle: &tauri::AppHandle) {
    let _ = RegKey::predef(HKEY_CURRENT_USER).open_subkey("Software\\ReportQA\\License")
        .and_then(|k| k.delete_value("LicenseData"));
    if let Some(p) = get_appdata_path(app_handle) {
        let _ = std::fs::remove_file(p);
    }
    let _ = std::fs::remove_file(get_programdata_path());
}

fn get_last_run_time(_app_handle: &tauri::AppHandle) -> u64 {
    RegKey::predef(HKEY_CURRENT_USER)
        .open_subkey("Software\\ReportQA\\License")
        .ok()
        .and_then(|k| k.get_value::<String, _>("LastRunTime").ok())
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0)
}

fn update_last_run_time(time: u64) {
    if let Ok((k, _)) = RegKey::predef(HKEY_CURRENT_USER).create_subkey("Software\\ReportQA\\License") {
        let _ = k.set_value("LastRunTime", &time.to_string());
    }
}

pub fn verify_registration_code(code: &str) -> Result<LicensePayload, String> {
    let parts: Vec<&str> = code.trim().split('.').collect();
    if parts.len() != 2 {
        return Err("Invalid license payload packaging structure".to_string());
    }

    let payload_b64 = parts[0];
    let signature_b64 = parts[1];

    let payload_bytes = base64::Engine::decode(&base64::engine::general_purpose::STANDARD, payload_b64)
        .map_err(|_| "Payload string decoding error".to_string())?;

    let payload_str = String::from_utf8(payload_bytes)
        .map_err(|_| "Invalid character sequence in payload".to_string())?;

    let signature_bytes = base64::Engine::decode(&base64::engine::general_purpose::STANDARD, signature_b64)
        .map_err(|_| "Signature string decoding error".to_string())?;

    let pub_key = RsaPublicKey::from_pkcs1_pem(RSA_PUBLIC_KEY_PEM)
        .map_err(|e| format!("Failed to parse public key: {}", e))?;

    let mut hasher = Sha256::new();
    hasher.update(payload_str.as_bytes());
    let hashed = hasher.finalize();

    pub_key.verify(
        rsa::Pkcs1v15Sign::new::<rsa::sha2::Sha256>(),
        &hashed,
        &signature_bytes
    ).map_err(|_| "Cryptographic signature validation failed".to_string())?;

    let payload: LicensePayload = serde_json::from_str(&payload_str)
        .map_err(|e| format!("Invalid JSON payload: {}", e))?;

    Ok(payload)
}

fn verify_hardware(registered: &[String]) -> bool {
    let local = collect_fingerprints();
    let mut matches = 0;
    for i in 0..4 {
        if i < registered.len() && i < local.len() && registered[i] == local[i] {
            matches += 1;
        }
    }
    matches >= 3
}

fn parse_date_to_timestamp(d: &str) -> u64 {
    let parts: Vec<&str> = d.split('-').collect();
    if parts.len() != 3 { return 0; }
    let yr = parts[0].parse::<u64>().unwrap_or(2026);
    let mo = parts[1].parse::<u64>().unwrap_or(1);
    let dy = parts[2].parse::<u64>().unwrap_or(1);
    yr * 372 + mo * 31 + dy
}

pub fn check_license_status(app_handle: &tauri::AppHandle) -> LicenseInfo {
    let code_opt = load_registration_code(app_handle);
    if code_opt.is_none() {
        return LicenseInfo {
            is_activated: false,
            is_expired: false,
            license_id: String::new(),
            edition: "Trial".to_string(),
            expire_date: String::new(),
            permanent: false,
            features: vec![],
        };
    }

    let code = code_opt.unwrap();
    let payload = match verify_registration_code(&code) {
        Ok(p) => p,
        Err(_) => {
            return LicenseInfo {
                is_activated: false,
                is_expired: false,
                license_id: String::new(),
                edition: "Trial".to_string(),
                expire_date: String::new(),
                permanent: false,
                features: vec![],
            };
        }
    };

    if payload.product_id != "REPORT_QA" {
        return LicenseInfo { is_activated: false, is_expired: false, license_id: String::new(), edition: "Trial".to_string(), expire_date: String::new(), permanent: false, features: vec![] };
    }

    if !verify_hardware(&payload.fingerprints) {
        return LicenseInfo { is_activated: false, is_expired: false, license_id: String::new(), edition: "Trial".to_string(), expire_date: String::new(), permanent: false, features: vec![] };
    }

    let current_utc = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    let last_run = get_last_run_time(app_handle);
    if current_utc < last_run {
        return LicenseInfo { is_activated: false, is_expired: false, license_id: String::new(), edition: "Trial".to_string(), expire_date: String::new(), permanent: false, features: vec![] };
    }
    update_last_run_time(current_utc);

    let is_expired = if payload.permanent {
        false
    } else {
        let now_date = chrono::Utc::now().format("%Y-%m-%d").to_string();
        parse_date_to_timestamp(&now_date) > parse_date_to_timestamp(&payload.expire_date)
    };

    LicenseInfo {
        is_activated: true,
        is_expired,
        license_id: payload.license_id,
        edition: payload.edition,
        expire_date: payload.expire_date,
        permanent: payload.permanent,
        features: payload.features,
    }
}

/// Generates an offline registration code for this machine for development testing.
/// Signs it with the developer RSA private key.
pub fn generate_developer_code() -> Result<String, String> {
    let fps = collect_fingerprints();
    let payload = LicensePayload {
        license_id: "DEV-RQA-AUTO".to_string(),
        product_id: "REPORT_QA".to_string(),
        customer_id: "CUS_DEVELOPER".to_string(),
        fingerprints: fps,
        edition: "Enterprise".to_string(),
        features: vec![
            "PDF_EXPORT".to_string(),
            "WORD_EXPORT".to_string(),
            "AI".to_string(),
            "PLUGIN".to_string(),
        ],
        issue_date: "2026-06-29".to_string(),
        expire_date: "2036-06-29".to_string(),
        permanent: true,
        salt: "developer_auto_test".to_string(),
    };

    let payload_json = serde_json::to_string(&payload)
        .map_err(|e| format!("Serialization error: {}", e))?;

    let priv_key = RsaPrivateKey::from_pkcs8_pem(RSA_PRIVATE_KEY_PEM)
        .map_err(|e| format!("Failed to parse private key: {}", e))?;

    let mut hasher = Sha256::new();
    hasher.update(payload_json.as_bytes());
    let hashed = hasher.finalize();

    let signature = priv_key.sign(
        rsa::Pkcs1v15Sign::new::<rsa::sha2::Sha256>(),
        &hashed
    ).map_err(|e| format!("Signing error: {}", e))?;

    let sig_b64 = base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &signature);
    let payload_b64 = base64::Engine::encode(&base64::engine::general_purpose::STANDARD, payload_json.as_bytes());
    
    Ok(format!("{}.{}", payload_b64, sig_b64))
}
