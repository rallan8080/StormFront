import { IsEmail, MaxLength } from 'class-validator';

export class LoginDto {
  @IsEmail()
  email!: string;

  @MaxLength(72)
  password!: string;
}
