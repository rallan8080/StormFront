import { IsOptional, IsString, Length, Matches } from 'class-validator';

export class CreateCharacterDto {
  // Mirrors PlayerName in server/app/models.py.
  @Matches(/^[A-Za-z][A-Za-z0-9_-]*$/)
  @Length(3, 24)
  name!: string;

  @IsOptional()
  @IsString()
  description?: string;
}
