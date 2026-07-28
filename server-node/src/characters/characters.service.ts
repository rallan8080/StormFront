import { Injectable, NotImplementedException } from '@nestjs/common';
import { CreateCharacterDto } from './dto/create-character.dto';

// Not yet ported. Reference implementation: server/app/routers/characters.py
// + server/app/world.py (starting room, world seed).
@Injectable()
export class CharactersService {
  list(): never {
    throw new NotImplementedException(
      'characters.list not yet ported — see server/app/routers/characters.py',
    );
  }

  create(_dto: CreateCharacterDto): never {
    throw new NotImplementedException(
      'characters.create not yet ported — see server/app/routers/characters.py',
    );
  }
}
