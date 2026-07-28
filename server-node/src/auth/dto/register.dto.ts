import { IsEmail, Length } from 'class-validator';

export class RegisterDto {
  @IsEmail()
  email!: string;

  // 72 byte hard cap is bcrypt's input limit — mirrors RegisterRequest in
  // server/app/models.py.
  @Length(12, 72)
  password!: string;
}
