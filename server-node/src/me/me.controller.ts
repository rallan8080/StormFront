import { Controller, Get, NotImplementedException } from '@nestjs/common';

// Not yet ported. Reference implementation: server/app/routers/me.py +
// server/app/deps.py (bearer token -> current account resolution).
@Controller()
export class MeController {
  @Get('me')
  me(): never {
    throw new NotImplementedException(
      'me not yet ported — see server/app/routers/me.py',
    );
  }
}
