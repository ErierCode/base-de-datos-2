using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using DataOps.Api.Models;
using Microsoft.AspNetCore.Mvc;
using Microsoft.IdentityModel.Tokens;

namespace DataOps.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class AuthController : ControllerBase
{
    private readonly IConfiguration _config;

    public AuthController(IConfiguration config) => _config = config;

    [HttpPost("login")]
    [ProducesResponseType(typeof(LoginResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public ActionResult<LoginResponse> Login([FromBody] LoginRequest req)
    {
        var user = _config["Auth:DemoUser"] ?? "admin";
        var pass = _config["Auth:DemoPassword"] ?? "Admin123!";
        if (req.Username != user || req.Password != pass)
            return Unauthorized(new { message = "Credenciales inválidas." });

        var minutes = int.Parse(_config["Jwt:ExpiresMinutes"] ?? "480");
        var expires = DateTime.UtcNow.AddMinutes(minutes);
        var token = CreateToken(req.Username, expires);
        return Ok(new LoginResponse(token, expires));
    }

    private string CreateToken(string username, DateTime expires)
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_config["Jwt:Key"]!));
        var creds = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);
        var claims = new[]
        {
            new Claim(ClaimTypes.Name, username),
            new Claim(ClaimTypes.Role, "Operator")
        };
        var jwt = new JwtSecurityToken(
            issuer: _config["Jwt:Issuer"],
            audience: _config["Jwt:Audience"],
            claims: claims,
            expires: expires,
            signingCredentials: creds);
        return new JwtSecurityTokenHandler().WriteToken(jwt);
    }
}
