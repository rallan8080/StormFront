import { Injectable, NotImplementedException } from '@nestjs/common';
import { LoginDto } from './dto/login.dto';
import { RefreshDto } from './dto/refresh.dto';
import { RegisterDto } from './dto/register.dto';

// Not yet ported. Reference implementation: server/app/routers/auth.py +
// server/app/security.py (bcrypt hashing, JWT issue/verify). Node
// equivalents are already in package.json (bcryptjs, jsonwebtoken) but not
// wired up yet.
@Injectable()
export class AuthService {
  register(_dto: RegisterDto): never {
    throw new NotImplementedException(
      'auth.register not yet ported — see server/app/routers/auth.py',
    );
  }

  login(_dto: LoginDto): never {
    throw new NotImplementedException(
      'auth.login not yet ported — see server/app/routers/auth.py',
    );
  }

  refresh(_dto: RefreshDto): never {
    throw new NotImplementedException(
      'auth.refresh not yet ported — see server/app/routers/auth.py',
    );
  }
}
