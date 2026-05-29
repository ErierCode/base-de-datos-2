using System.Security.Cryptography;
using System.Text;

namespace DataOps.Api.Services;

/// <summary>Cifrado AES-GCM para password_ciphertext (Módulo 1 — nunca texto plano).</summary>
public sealed class CredentialProtector
{
    private const string Algo = "AES-GCM-v1";
    private readonly byte[] _key;

    public CredentialProtector(IConfiguration config)
    {
        var b64 = config["CredentialEncryption:KeyBase64"];
        if (!string.IsNullOrWhiteSpace(b64))
        {
            _key = Convert.FromBase64String(b64);
        }
        else
        {
            var seed = config["Jwt:Key"] ?? "dcc-default-encryption-seed-32b!";
            _key = SHA256.HashData(Encoding.UTF8.GetBytes(seed));
        }
    }

    public string Algorithm => Algo;

    public byte[] Encrypt(string plain)
    {
        var nonce = RandomNumberGenerator.GetBytes(12);
        var plainBytes = Encoding.UTF8.GetBytes(plain);
        var cipher = new byte[plainBytes.Length];
        var tag = new byte[16];
        using var aes = new AesGcm(_key, 16);
        aes.Encrypt(nonce, plainBytes, cipher, tag);
        var blob = new byte[nonce.Length + tag.Length + cipher.Length];
        Buffer.BlockCopy(nonce, 0, blob, 0, nonce.Length);
        Buffer.BlockCopy(tag, 0, blob, nonce.Length, tag.Length);
        Buffer.BlockCopy(cipher, 0, blob, nonce.Length + tag.Length, cipher.Length);
        return blob;
    }

    public string Decrypt(byte[] blob)
    {
        if (blob.Length < 28) throw new InvalidOperationException("Blob cifrado inválido.");
        var nonce = blob.AsSpan(0, 12);
        var tag = blob.AsSpan(12, 16);
        var cipher = blob.AsSpan(28);
        var plain = new byte[cipher.Length];
        using var aes = new AesGcm(_key, 16);
        aes.Decrypt(nonce, cipher, tag, plain);
        return Encoding.UTF8.GetString(plain);
    }
}
