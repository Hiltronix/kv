require "kemal-basic-auth"

# Key the rate limiter by source IP, never the ephemeral TCP port.
class KVBasicAuthHandler < Kemal::BasicAuth::Handler
  private def remote_key(context) : String?
    address = context.request.remote_address
    case address
    when Socket::IPAddress
      address.address
    else
      address.try(&.to_s)
    end
  end
end

module KVSecurity
  MAX_JSON_BYTES = 65_536

  def self.read_json_body(body : IO?) : String
    return "{}" unless body
    result = IO::Memory.new
    bytes = IO.copy(body, result, MAX_JSON_BYTES + 1)
    raise "Request body too large" if bytes > MAX_JSON_BYTES
    result.to_s
  end
end
